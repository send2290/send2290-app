import os
import datetime
import json
import io
import logging
import zipfile  # Add this import
from functools import wraps
from flask import Flask, request, jsonify, make_response, send_file, Response
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base
import boto3
import botocore
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from dotenv import load_dotenv
from xml_builder import build_2290_xml
import firebase_admin
from firebase_admin import credentials, auth
from Audit.enhanced_audit import IRS2290AuditLogger

# Function to load form positions from JSON file
def load_form_positions():
    try:
        positions_file = os.path.join(os.path.dirname(__file__), "form_positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                return json.load(f)
        else:
            print("⚠️ Warning: form_positions.json not found, using default positions")
            return {}
    except Exception as e:
        print(f"⚠️ Error loading form positions: {str(e)}")
        return {}

# Load form positions on startup
FORM_POSITIONS = load_form_positions()

load_dotenv()

# Hybrid database configuration
if os.getenv("FLASK_ENV") == "development":
    DATABASE_URL = "sqlite:///./send2290.db"
    print("🔧 Development mode: Using SQLite database")
else:
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set!")
    print("🚀 Production mode: Using PostgreSQL database")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Submission(Base):
    __tablename__ = 'submissions'
    id         = Column(Integer, primary_key=True, index=True)
    user_uid   = Column(String, index=True)
    month      = Column(String, index=True)
    xml_s3_key = Column(String)
    pdf_s3_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    form_data  = Column(Text)  # Use Text for SQLite, not JSON

class FilingsDocument(Base):
    __tablename__ = 'filings_documents'
    id            = Column(Integer, primary_key=True, index=True)
    filing_id     = Column(Integer, index=True)
    user_uid      = Column(String, index=True)
    document_type = Column(String)
    s3_key        = Column(String)
    uploaded_at   = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Determine environment and initialize appropriate audit loggers
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
IS_PRODUCTION = ENVIRONMENT == 'production' or os.getenv('RENDER') is not None

# Initialize both audit loggers
if IS_PRODUCTION:
    # Production environment
    enhanced_audit = IRS2290AuditLogger('production')
    audit_log_file = 'productionaudit.log'
else:
    # Local development environment
    enhanced_audit = IRS2290AuditLogger('local')
    audit_log_file = 'localaudit.log'

# Set up audit logging for IRS compliance
audit_logger = logging.getLogger('audit')
# Clear existing handlers
for handler in audit_logger.handlers[:]:
    audit_logger.removeHandler(handler)

# Add new handler with environment-specific file
audit_handler = logging.FileHandler(audit_log_file)
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

def log_admin_action(action, details):
    """Enhanced admin action logging with environment context"""
    user_email = getattr(request, 'user', {}).get('email', 'UNKNOWN_USER')
    
    # Log to both old and new systems during transition
    audit_logger.info(f"ADMIN_ACTION: {action} | USER: {user_email} | ENV: {'PROD' if IS_PRODUCTION else 'LOCAL'} | DETAILS: {details}")
    enhanced_audit.log_admin_action(user_email, action, details)

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:3000",
        "http://localhost:3001",  # Add port 3001
        "https://send2290.com",
        "https://www.send2290.com"
    ]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

# Firebase Admin initialization
try:
    if os.getenv("FLASK_ENV") == "development":
        # Development: use local service account file
        service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
        if os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            raise FileNotFoundError("firebase-service-account.json not found in backend folder for development")
    else:
        # Production: use environment variable JSON
        firebase_json = os.getenv('FIREBASE_ADMIN_KEY_JSON')
        if not firebase_json:
            raise ValueError("FIREBASE_ADMIN_KEY_JSON environment variable not set")
        
        # Parse the JSON string from environment variable
        firebase_config = json.loads(firebase_json)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    
    firebase_auth = auth
    print("✅ Firebase Admin initialized successfully")
    
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    raise

s3 = boto3.client(
    's3',
    aws_access_key_id     = os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name           = os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
    config=botocore.client.Config(signature_version='s3v4')
)
BUCKET = os.getenv('FILES_BUCKET')

def verify_firebase_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return make_response("", 200)
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header missing or malformed"}), 401
        token = auth_header.split('Bearer ')[1]
        try:
            decoded = firebase_auth.verify_id_token(token)
            request.user = decoded
        except Exception as e:
            return jsonify({"error": "Invalid or expired token", "details": str(e)}), 403
        return f(*args, **kwargs)
    return wrapper

def verify_admin_token(f):
    """
    Decorator to verify admin access for sensitive operations.
    Required for IRS compliance - only authorized personnel can access taxpayer data.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # First verify the Firebase token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", "No valid Bearer token provided")
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = firebase_auth.verify_id_token(token)
            
            # Check if user is admin - GET FROM ENVIRONMENT VARIABLE
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@send2290.com')  # Use environment variable
            admin_emails = [admin_email, 'admin@send2290.com']  # Fallback admin
            
            if decoded_token.get('email') not in admin_emails:
                log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", f"Non-admin user {decoded_token.get('email')} attempted admin access")
                return jsonify({'error': 'Admin access required'}), 403
                
            request.user = decoded_token
            return f(*args, **kwargs)
        except Exception as e:
            log_admin_action("INVALID_TOKEN_ATTEMPT", f"Invalid token: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
    return decorated

@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Send2290 API is up"}), 200

@app.route("/protected", methods=["GET"])
@verify_firebase_token
def protected():
    return jsonify({"message": f"Hello, {request.user.get('email')}!"}), 200

@app.route("/build-xml", methods=["POST", "OPTIONS"])
@verify_firebase_token
def generate_xml():
    if request.method == "OPTIONS":
        return make_response(jsonify({}), 200)

    data = request.get_json() or {}

    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    # Group vehicles by month - FIX: use 'used_month' not 'used_in_month'
    vehicles = data.get('vehicles', [])
    vehicles_by_month = {}
    
    for vehicle in vehicles:
        month = vehicle.get('used_month', data.get('used_on_july', ''))
        if month not in vehicles_by_month:
            vehicles_by_month[month] = []
        vehicles_by_month[month].append(vehicle)
    
    if not vehicles_by_month:
        return jsonify({"error": "No vehicles found"}), 400

    created_submissions = []
    generated_xmls = {}
    
    db = SessionLocal()
    try:
        # Create separate XML for each month
        for month, month_vehicles in vehicles_by_month.items():
            # Create form data for this month's vehicles
            month_data = data.copy()
            month_data['vehicles'] = month_vehicles
            month_data['used_on_july'] = month
            
            try:
                xml_data = build_2290_xml(month_data)
            except Exception as e:
                app.logger.error("Error building XML for month %s: %s", month, e, exc_info=True)
                continue

            if isinstance(xml_data, bytes):
                xml_data = xml_data.decode('utf-8', errors='ignore')

            # Save XML file with month identifier
            xml_path = os.path.join(os.path.dirname(__file__), f"form2290_{month}.xml")
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_data)

            xml_key = f"{request.user['uid']}/{month}/form2290.xml"
            try:
                with open(xml_path, 'rb') as xml_file:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=xml_key,
                        Body=xml_file,
                        ServerSideEncryption='aws:kms'
                    )
            except Exception as e:
                app.logger.error("S3 XML upload failed for month %s: %s", month, e, exc_info=True)

            # Create submission record for this month
            submission = Submission(
                user_uid=request.user['uid'],
                month=month,
                xml_s3_key=xml_key,
                form_data=json.dumps(month_data)
            )
            db.add(submission)
            db.commit()
            db.refresh(submission)

            db.add(FilingsDocument(
                filing_id=submission.id,
                user_uid=request.user['uid'],
                document_type='xml',
                s3_key=xml_key,
                uploaded_at=datetime.datetime.utcnow()
            ))
            
            created_submissions.append({
                'id': submission.id,
                'month': month,
                'vehicle_count': len(month_vehicles),
                'xml_key': xml_key
            })
            generated_xmls[month] = xml_data

        db.commit()
        
        # Log user submission
        try:
            enhanced_audit.log_user_action(
                user_id=request.user['uid'],
                action='FORM_SUBMISSION',
                form_data=data,
                ein=data.get('ein'),
                tax_year=data.get('tax_year', '2025')
            )
        except Exception as e:
            app.logger.error(f"Enhanced audit logging failed: {e}")
        
        # Return success response
        return jsonify({
            "success": True,
            "message": f"Generated XML for {len(created_submissions)} month(s)",
            "submissions": created_submissions,
            "total_files": len(created_submissions)
        }), 200
    
    except Exception as e:
        # Catch-all exception handler to prevent returning None
        app.logger.error("Unexpected error in build_xml: %s", e, exc_info=True)
        enhanced_audit.log_error_event(
            user_email=request.user.get('email', 'unknown'),
            error_type="XML_PROCESSING_ERROR",
            error_message=f"Unexpected error during XML submission: {str(e)}",
            endpoint="/build-xml"
        )
        return jsonify({
            "error": "An unexpected error occurred during XML generation",
            "details": "Please try again or contact support if the issue persists"
        }), 500
    
    finally:
        db.close()

@app.route("/download-xml", methods=["GET"])
@verify_firebase_token
def download_xml():
    xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
    if not os.path.exists(xml_path):
        return jsonify({"error": "XML not generated yet"}), 404
    return send_file(xml_path, mimetype="application/xml", as_attachment=True)

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    """
    Legacy PDF generation route - uses hardcoded positions for simple centered layout.
    For production forms, use /build-pdf which uses dynamic positions from form_positions.json
    """
    data = request.get_json() or {}
    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
    if not os.path.exists(template_path):
        return jsonify({"error": "Template not found"}), 500

    try:
        template = PdfReader(open(template_path, "rb"), strict=False)
    except Exception as e:
        return jsonify({"error": f"Failed to read template PDF: {str(e)}"}), 500

    # Calculate total tax amount from vehicles
    vehicles = data.get('vehicles', [])
    total_tax = sum(float(v.get('tax_amount', 0)) for v in vehicles)

    writer = PdfWriter()
    overlays = []

    for pg_idx in range(len(template.pages)):
        if pg_idx == 0:
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            
            # Business Name (larger font)
            can.setFont("Helvetica-Bold", 16)
            can.drawCentredString(306, 396, data.get("business_name", ""))
            
            # Address
            can.setFont("Helvetica", 14)
            can.drawCentredString(306, 376, data.get("address", ""))
            
            # EIN
            can.drawCentredString(306, 356, f"EIN: {data.get('ein', '')}")
            
            # Total Tax Amount
            can.setFont("Helvetica-Bold", 14)
            can.drawCentredString(306, 336, f"Total Tax: ${total_tax:,.2f}")
            
            # Vehicle Count
            can.setFont("Helvetica", 12)
            can.drawCentredString(306, 316, f"Vehicles: {len(vehicles)}")
            
            can.save()
            packet.seek(0)
            overlay_page = PdfReader(packet).pages[0]
            overlays.append(overlay_page)
        else:
            overlays.append(None)

    for idx, page in enumerate(template.pages):
        if overlays[idx]:
            page.merge_page(overlays[idx])
        writer.add_page(page)

    out_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "form2290_filled.pdf")
    with open(out_path, "wb") as f_out:
        writer.write(f_out)

    return send_file(out_path, as_attachment=True, download_name="form2290.pdf")

@app.route('/api/my-documents', methods=['GET'])
@verify_firebase_token
def list_my_documents():
    user_uid = request.user['uid']
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT filing_id, document_type, s3_key, uploaded_at
                  FROM filings_documents
                 WHERE user_uid = :uid
                 ORDER BY uploaded_at DESC
            """),
            {"uid": user_uid}
        ).fetchall()

        documents = []
        for row in rows:
            filing_id, doc_type, s3_key, uploaded_at = row
            url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': BUCKET,
                    'Key': s3_key
                },
                ExpiresIn=900
            )
            documents.append({
                "filing_id": str(filing_id),
                "type": doc_type,
                "uploaded_at": str(uploaded_at) if uploaded_at else None,
                "url": url
            })

        return jsonify({"documents": documents})
    finally:
        db.close()

@app.route("/build-pdf", methods=["POST", "OPTIONS"])
@verify_firebase_token
def build_pdf():
    if request.method == "OPTIONS":
        return make_response(jsonify({}), 200)
    
    data = request.get_json() or {}

    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    user_uid = request.user['uid']
    
    # Extract Part I tax summary data from frontend
    frontend_part_i = data.get('partI', {})
    
    # Group vehicles by month - FIX: use 'used_month' not 'used_in_month'
    vehicles = data.get('vehicles', [])
    vehicles_by_month = {}
    
    for idx, vehicle in enumerate(vehicles):
        month = vehicle.get('used_month', data.get('used_on_july', ''))
        if month not in vehicles_by_month:
            vehicles_by_month[month] = []
        vehicles_by_month[month].append(vehicle)
    
    if not vehicles_by_month:
        return jsonify({"error": "No vehicles found"}), 400

    created_files = []
    
    db = SessionLocal()
    try:
        template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
        if not os.path.exists(template_path):
            return jsonify({"error": "Template not found"}), 500
        
        # Process each month separately
        for month, month_vehicles in vehicles_by_month.items():
            print(f"📅 Processing month {month} with {len(month_vehicles)} vehicles")
            
            # Create form data for this month
            month_data = data.copy()
            month_data['vehicles'] = month_vehicles
            month_data['used_on_july'] = month
            
            # Calculate vehicle statistics for this month only
            total_reported = len(month_vehicles)
            total_suspended = len([v for v in month_vehicles if v.get("category") == "W"])
            total_taxable = total_reported - total_suspended
            
            # Add calculated statistics to month data
            month_data["total_reported_vehicles"] = str(total_reported)
            month_data["total_suspended_vehicles"] = str(total_suspended) 
            month_data["total_taxable_vehicles"] = str(total_taxable)
            
            weight_categories_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']
            
            # Group frontend calculations by month instead of recalculating
            print(f"💰 Grouping frontend calculations for month {month}")
            
            # Get frontend category and grand total data
            frontend_category_data = data.get('categoryData', {})
            frontend_grand_totals = data.get('grandTotals', {})
            
            total_tax = 0
            
            for cat in weight_categories_list:
                cat_lower = cat.lower()
                
                # Count vehicles in this month for this category
                regular_vehicles = [v for v in month_vehicles if v.get("category") == cat and not v.get("is_logging", False)]
                logging_vehicles = [v for v in month_vehicles if v.get("category") == cat and v.get("is_logging", False)]
                
                regular_count = len(regular_vehicles)
                logging_count = len(logging_vehicles)
                
                month_data[f"count_{cat_lower}_regular"] = str(regular_count)
                month_data[f"count_{cat_lower}_logging"] = str(logging_count)
                
                # Use frontend's per-vehicle rates and calculate only for this month's vehicles
                if cat in frontend_category_data:
                    frontend_cat_data = frontend_category_data[cat]
                    
                    # Determine if this is annual (July) or partial-period tax
                    month_num = int(month[-2:]) if month and len(month) >= 2 else 0
                    is_annual_month = (month_num == 7)  # July = annual tax
                    
                    if is_annual_month:
                        # Use annual tax rates for July
                        regular_per_vehicle_rate = frontend_cat_data.get('regularAnnualTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                        logging_per_vehicle_rate = frontend_cat_data.get('loggingAnnualTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                        tax_type = "annual"
                    else:
                        # Use partial-period tax rates for all other months
                        regular_per_vehicle_rate = frontend_cat_data.get('regularPartialTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                        logging_per_vehicle_rate = frontend_cat_data.get('loggingPartialTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                        tax_type = "partial"
                    
                    # Calculate month-specific totals using frontend rates
                    regular_total_tax = regular_count * regular_per_vehicle_rate
                    logging_total_tax = logging_count * logging_per_vehicle_rate
                    
                    print(f"📋 Month {month} ({tax_type}) Category {cat}: {regular_count} regular × ${regular_per_vehicle_rate:.2f} = ${regular_total_tax:.2f}, {logging_count} logging × ${logging_per_vehicle_rate:.2f} = ${logging_total_tax:.2f}")
                else:
                    # No vehicles of this category
                    regular_total_tax = 0
                    logging_total_tax = 0
                    regular_per_vehicle_rate = 0
                    logging_per_vehicle_rate = 0
                
                total_category_tax = regular_total_tax + logging_total_tax
                total_tax += total_category_tax
                
                month_data[f"amount_{cat_lower}"] = f"{total_category_tax:.2f}"
                month_data[f"amount_{cat_lower}_regular"] = f"{regular_total_tax:.2f}"
                month_data[f"amount_{cat_lower}_logging"] = f"{logging_total_tax:.2f}"
                
                # Add per-vehicle rates for column 2 display
                if regular_count > 0:
                    month_data[f"tax_partial_{cat_lower}_regular"] = f"{regular_per_vehicle_rate:.2f}"
                if logging_count > 0:
                    month_data[f"tax_partial_{cat_lower}_logging"] = f"{logging_per_vehicle_rate:.2f}"
            
            # Add category W suspended vehicle counts for this month
            w_regular_count = len([v for v in month_vehicles if v.get("category") == "W" and not v.get("is_logging", False)])
            w_logging_count = len([v for v in month_vehicles if v.get("category") == "W" and v.get("is_logging", False)])
            
            month_data["count_w_suspended_non_logging"] = str(w_regular_count)
            month_data["count_w_suspended_logging"] = str(w_logging_count)
            
            if w_regular_count > 0 or w_logging_count > 0:
                print(f"📋 Month {month} Category W (Suspended): Regular={w_regular_count} + Logging={w_logging_count}")
            
            # Simple month-specific Part I calculation
            
            # TEMPORARILY DISABLE CREDITS TO FIX PART I CALCULATIONS
            credits = 0.0  # float(data.get('tax_credits', 0))
            additional_tax = 0.00
            total_tax_with_additional = total_tax + additional_tax
            
            # No credit distribution needed when credits = 0
            month_credits = 0.0
            
            balance_due = max(0, total_tax_with_additional - month_credits)
            
            # Create month-specific Part I data
            month_part_i = {
                'line2_tax': total_tax,
                'line3_increase': additional_tax,
                'line4_total': total_tax_with_additional,
                'line5_credits': month_credits,
                'line6_balance': balance_due
            }
            
            for field_name, field_value in month_part_i.items():
                month_data[field_name] = f"{field_value:.2f}"
            
            # Add dynamic VIN fields to month data
            print(f"🔍 Adding VIN data for {len(month_vehicles)} vehicles to month_data:")
            for i, vehicle in enumerate(month_vehicles, 1):
                if i <= 24:  # Support up to 24 VINs as defined in positions
                    vin_value = vehicle.get("vin", "")
                    category_value = vehicle.get("category", "")
                    is_agricultural = vehicle.get("is_agricultural", False)
                    mileage_5000_or_less = vehicle.get("mileage_5000_or_less", False)
                    is_suspended = vehicle.get("is_suspended", False)
                    
                    month_data[f"vin_{i}"] = vin_value
                    month_data[f"vin_{i}_category"] = category_value
                    print(f"  vin_{i}: '{vin_value}' -> category: '{category_value}' | agricultural: {is_agricultural} | mileage≤5k: {mileage_5000_or_less} | suspended: {is_suspended}")
            
            # Generate XML first
            try:
                xml_data = build_2290_xml(month_data)
            except Exception as e:
                app.logger.error("Error building XML for month %s: %s", month, e, exc_info=True)
                continue

            if isinstance(xml_data, bytes):
                xml_data = xml_data.decode('utf-8', errors='ignore')

            xml_key = f"{user_uid}/{month}/form2290.xml"
            xml_path = os.path.join(os.path.dirname(__file__), f"form2290_{month}.xml")
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_data)

            # Upload XML to S3
            s3_upload_success = False
            try:
                with open(xml_path, 'rb') as xml_file:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=xml_key,
                        Body=xml_file,
                        ServerSideEncryption='aws:kms'
                    )
                s3_upload_success = True
            except Exception as e:
                app.logger.error("S3 XML upload failed for month %s: %s", month, e, exc_info=True)
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="S3_UPLOAD_FAILED",
                    error_message=f"Failed to upload XML to S3: {str(e)}",
                    endpoint="/build-xml"
                )
                # Continue processing but log the failure

            # Create submission record with original frontend data (preserves Part I tax calculation)
            submission_data = data.copy()  # Use original data that contains frontend's partI calculation
            submission_data['processed_month'] = month  # Add which month this submission represents
            submission_data['month_vehicles'] = month_vehicles  # Add vehicles for this specific month
            
            submission = Submission(
                user_uid=user_uid,
                month=month,
                xml_s3_key=xml_key,
                form_data=json.dumps(submission_data)  # Save original frontend data, not just month_data
            )
            db.add(submission)
            db.commit()
            db.refresh(submission)
            filing_id = submission.id

            # Add XML document record
            db.add(FilingsDocument(
                filing_id=filing_id,
                user_uid=user_uid,
                document_type='xml',
                s3_key=xml_key,
                uploaded_at=datetime.datetime.utcnow()
            ))
            db.commit()

            # Generate PDF for this month using multi-page field positioning
            # Load a fresh template for each month to avoid overlapping layers
            template = PdfReader(open(template_path, "rb"), strict=False)
            writer = PdfWriter()

            # Process each page in the template (like the test PDF function)
            for page_num in range(1, len(template.pages) + 1):
                print(f"Processing page {page_num} for month {month}")
                
                # Create overlay for this page
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                
                # Get all fields that should appear on this page
                fields_on_page = []
                for field_name, field_data in FORM_POSITIONS.items():
                    # Skip special field types that don't have pages array
                    if "x" not in field_data or "y" not in field_data:
                        continue
                        
                    # Handle both old single page format and new pages array format
                    field_pages = []
                    if "pages" in field_data and isinstance(field_data["pages"], list):
                        field_pages = field_data["pages"]
                    elif "page" in field_data:
                        field_pages = [field_data["page"]]
                    else:
                        field_pages = [1]  # Default to page 1
                    
                    if page_num in field_pages:
                        fields_on_page.append(field_name)
                
                print(f"Fields on page {page_num}: {fields_on_page}")
                
                # Render fields for this page
                for field_name in fields_on_page:
                    field_data = FORM_POSITIONS[field_name]
                    
                    # Skip fields that don't have x,y coordinates (special field types)
                    if "x" not in field_data or "y" not in field_data:
                        print(f"Skipping special field type: {field_name}")
                        continue
                    
                    # Get position for this specific page (handle page-specific positions)
                    pos_x = field_data["x"]
                    pos_y = field_data["y"] 
                    x_positions = field_data.get("x_positions")
                    
                    # Check for page-specific position overrides
                    if "pagePositions" in field_data and str(page_num) in field_data["pagePositions"]:
                        page_override = field_data["pagePositions"][str(page_num)]
                        if "x" in page_override:
                            pos_x = page_override["x"]
                        if "y" in page_override:
                            pos_y = page_override["y"]
                        if "x_positions" in page_override:
                            x_positions = page_override["x_positions"]
                    
                    # Apply offsets
                    pdf_x_offset = field_data.get("pdf_x_offset", 0)
                    pdf_y_offset = field_data.get("pdf_y_offset", 0)
                    
                    can.setFont(field_data["font"], field_data["size"])
                    
                    # Render based on field type
                    if field_name == "tax_year":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("tax_year", "2025"))
                        
                    elif field_name == "business_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("business_name", ""))
                        
                    elif field_name == "address":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("address", ""))
                        
                    elif field_name == "city_state_zip":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        city = data.get("city", "")
                        state = data.get("state", "")
                        zip_code = data.get("zip", "")
                        city_state_zip = f"{city}, {state} {zip_code}"
                        can.drawString(final_x, final_y, city_state_zip)
                        
                    elif field_name == "ein_digits" and x_positions:
                        ein = data.get("ein", "").replace("-", "")
                        for i, digit in enumerate(ein):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, digit)
                    
                    elif field_name.startswith("vin_") and not field_name.endswith("_category") and x_positions:
                        # Handle VIN fields with character-by-character spacing
                        vin_value = month_data.get(field_name, "")
                        print(f"🖊️ Rendering VIN field '{field_name}' = '{vin_value}' on page {page_num}")
                        for i, char in enumerate(vin_value):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, char)
                    
                    # NEW FIELDS - Address fields
                    elif field_name == "address_line2":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("address_line2", ""))
                        
                    elif field_name == "business_name_line2":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("business_name_line2", ""))
                        
                    elif field_name == "city":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("city", ""))
                        
                    elif field_name == "state":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("state", ""))
                        
                    elif field_name == "zip":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("zip", ""))
                    
                    # Amendment fields
                    elif field_name == "amended_month":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("amended_month", ""))
                        
                    elif field_name == "reasonable_cause_explanation":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("reasonable_cause_explanation", ""))
                        
                    elif field_name == "vin_correction_explanation":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("vin_correction_explanation", ""))
                        
                    elif field_name == "special_conditions":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("special_conditions", ""))
                    
                    # Officer information
                    elif field_name == "officer_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("officer_name", ""))
                        
                    elif field_name == "officer_title":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("officer_title", ""))
                        
                    elif field_name == "officer_ssn":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        ssn = data.get("officer_ssn", "")
                        # Format SSN with dashes for display
                        if len(ssn) == 9 and ssn.isdigit():
                            ssn = f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
                        can.drawString(final_x, final_y, ssn)
                        
                    elif field_name == "taxpayer_pin":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("taxpayer_pin", ""))
                        

                    # Preparer information
                    elif field_name == "preparer_name":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_name", ""))
                        
                    elif field_name == "preparer_ptin":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_ptin", ""))
                        
                    elif field_name == "date_prepared":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("date_prepared", ""))
                        
                    elif field_name == "preparer_firm_name":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_firm_name", ""))
                        
                    elif field_name == "preparer_firm_ein":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            ein = data.get("preparer_firm_ein", "")
                            # Format EIN with dash for display
                            if len(ein) == 9 and ein.isdigit():
                                ein = f"{ein[:2]}-{ein[2:]}"
                            can.drawString(final_x, final_y, ein)
                        
                    elif field_name == "preparer_firm_address":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_firm_address", ""))
                        
                    elif field_name == "preparer_firm_citystatezip":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_firm_citystatezip", ""))
                        
                    elif field_name == "preparer_firm_phone":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_firm_phone", ""))
                    
                    # Third party designee information
                    elif field_name == "designee_name":
                        if data.get("consent_to_disclose", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("designee_name", ""))
                        
                    elif field_name == "designee_phone":
                        if data.get("consent_to_disclose", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("designee_phone", ""))
                        
                    elif field_name == "designee_pin":
                        if data.get("consent_to_disclose", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("designee_pin", ""))
                    
                    # Signature fields
                    elif field_name == "signature":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("signature", ""))
                        
                    elif field_name == "printed_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("printed_name", ""))
                        
                    elif field_name == "signature_date":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("signature_date", ""))
                    
                    # Payment fields
                    elif field_name == "eftps_routing":
                        if data.get("payEFTPS", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("eftps_routing", ""))
                        
                    elif field_name == "eftps_account":
                        if data.get("payEFTPS", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("eftps_account", ""))
                        
                    elif field_name == "account_type":
                        if data.get("payEFTPS", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("account_type", ""))
                        
                    elif field_name == "payment_date":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("payment_date", ""))
                        
                    elif field_name == "taxpayer_phone":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("taxpayer_phone", ""))
                    
                    # Credit card payment fields
                    elif field_name == "card_holder":
                        if data.get("payCard", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("card_holder", ""))
                        
                    elif field_name == "card_number":
                        if data.get("payCard", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            # Mask card number for security (show only last 4 digits)
                            card_num = data.get("card_number", "")
                            if len(card_num) > 4:
                                masked = "*" * (len(card_num) - 4) + card_num[-4:]
                                can.drawString(final_x, final_y, masked)
                            else:
                                can.drawString(final_x, final_y, card_num)
                        
                    elif field_name == "card_exp":
                        if data.get("payCard", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("card_exp", ""))
                        
                    elif field_name == "card_cvv":
                        if data.get("payCard", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            # Don't render CVV for security
                            can.drawString(final_x, final_y, "***")
                    
                    # Email field
                    elif field_name == "email":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("email", ""))
                        
                    elif field_name == "used_on_july" and x_positions:
                        used_on_july = month_data.get("used_on_july", "")
                        print(f"🖊️ Rendering month field '{field_name}' = '{used_on_july}' on page {page_num}")
                        for i, digit in enumerate(used_on_july):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, digit)
                        
                    elif field_name == "used_on_july":
                        # Fallback for when x_positions is not available
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        used_on_july = month_data.get("used_on_july", "")
                        print(f"🖊️ Rendering month field '{field_name}' (fallback) = '{used_on_july}' on page {page_num}")
                        can.drawString(final_x, final_y, used_on_july)
                    
                    # Additional checkbox fields
                    elif field_name == "checkbox_has_disposals":
                        if data.get("has_disposals", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                            
                    elif field_name == "checkbox_preparer_self_employed":
                        if data.get("include_preparer", False) and data.get("preparer_self_employed", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                            
                    elif field_name == "checkbox_consent_to_disclose":
                        if data.get("consent_to_disclose", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                            
                    elif field_name == "checkbox_payEFTPS":
                        if data.get("payEFTPS", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                            
                    elif field_name == "checkbox_payCard":
                        if data.get("payCard", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                    
                    elif field_name.startswith("checkbox_"):
                        # Handle checkboxes
                        should_check = False
                        if field_name == "checkbox_address_change":
                            should_check = data.get("address_change", False)
                        elif field_name == "checkbox_vin_correction":
                            should_check = data.get("vin_correction", False)
                        elif field_name == "checkbox_amended_return":
                            should_check = data.get("amended_return", False)
                        elif field_name == "checkbox_final_return":
                            should_check = data.get("final_return", False)
                        elif field_name == "checkbox_agricultural":
                            # Check if any vehicle in this month is agricultural
                            should_check = any(v.get("is_agricultural", False) for v in month_vehicles)
                            print(f"🔍 Checking agricultural: {[v.get('is_agricultural', False) for v in month_vehicles]} -> {should_check}")
                        elif field_name == "checkbox_non_agricultural":
                            # Check if any vehicle in this month is non-agricultural with ≤5,000 miles
                            should_check = any(v.get("mileage_5000_or_less", False) and not v.get("is_agricultural", False) 
                                             for v in month_vehicles)
                            print(f"🔍 Checking non-agricultural ≤5k miles: {[(v.get('mileage_5000_or_less', False), v.get('is_agricultural', False)) for v in month_vehicles]} -> {should_check}")
                        elif field_name == "checkbox_suspended":
                            # Check if any vehicle in this month is suspended (category W)
                            should_check = any(v.get("category", "") == "W" or v.get("is_suspended", False) 
                                             for v in month_vehicles)
                            print(f"🔍 Checking suspended: {[(v.get('category', ''), v.get('is_suspended', False)) for v in month_vehicles]} -> {should_check}")
                        
                        if should_check:
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                            print(f"✅ Checking checkbox '{field_name}' on page {page_num} - condition met")
                    
                    # NEW VEHICLE STATISTICS FIELDS
                    elif field_name == "total_reported_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, month_data.get("total_reported_vehicles", ""))
                        
                    elif field_name == "total_suspended_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, month_data.get("total_suspended_vehicles", ""))
                        
                    elif field_name == "total_taxable_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, month_data.get("total_taxable_vehicles", ""))
                    
                    # DYNAMIC VIN FIELDS
                    elif field_name.startswith("vin_") and not field_name.endswith("_category") and not x_positions:
                        # Handle VIN fields (vin_1, vin_2, etc.) - fallback when no x_positions available
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        vin_value = month_data.get(field_name, "")
                        if vin_value:  # Only render if VIN exists
                            can.drawString(final_x, final_y, vin_value)
                            
                    elif field_name.startswith("vin_") and field_name.endswith("_category"):
                        # Handle VIN category fields (vin_1_category, vin_2_category, etc.)
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        category_value = month_data.get(field_name, "")
                        print(f"🖊️ Rendering category field '{field_name}' = '{category_value}' on page {page_num}")
                        if category_value:  # Only render if category exists
                            can.drawString(final_x, final_y, category_value)
                    
                    elif field_name == "month_checkboxes":
                        # Handle month checkboxes
                        month_last_two = month[-2:] if len(month) >= 2 else '07'
                        if month_last_two in field_data:
                            month_pos = field_data[month_last_two]
                            final_x = month_pos["x"] + pdf_x_offset
                            final_y = month_pos["y"] + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                    
                    elif field_name == "vehicle_categories":
                        # Handle vehicle category counts
                        weight_counts = {}
                        for vehicle in month_vehicles:
                            category = vehicle.get('category', '')
                            if category:
                                weight_counts[category] = weight_counts.get(category, 0) + 1
                        
                        # Draw vehicle counts in appropriate category boxes
                        for category, count in weight_counts.items():
                            if category in field_data:
                                cat_pos = field_data[category]
                                final_x = cat_pos["x"] + pdf_x_offset
                                final_y = cat_pos["y"] + pdf_y_offset
                                can.drawString(final_x, final_y, str(count))
                    
                    elif field_name == "tax_lines":
                        # Handle Part I tax calculation lines using frontend-calculated values
                        if "line2_tax" in field_data:
                            line2_pos = field_data["line2_tax"]
                            final_x = line2_pos["x"] + pdf_x_offset
                            final_y = line2_pos["y"] + pdf_y_offset
                            can.setFont(line2_pos["font"], line2_pos["size"])
                            line2_value = month_data.get("line2_tax", f"{total_tax:.2f}")
                            can.drawRightString(final_x, final_y, line2_value)
                        
                        if "line3_increase" in field_data:
                            line3_pos = field_data["line3_increase"]
                            final_x = line3_pos["x"] + pdf_x_offset
                            final_y = line3_pos["y"] + pdf_y_offset
                            can.setFont(line3_pos["font"], line3_pos["size"])
                            line3_value = month_data.get("line3_increase", "0.00")
                            can.drawRightString(final_x, final_y, line3_value)
                        
                        if "line4_total" in field_data:
                            line4_pos = field_data["line4_total"]
                            final_x = line4_pos["x"] + pdf_x_offset
                            final_y = line4_pos["y"] + pdf_y_offset
                            can.setFont(line4_pos["font"], line4_pos["size"])
                            line4_value = month_data.get("line4_total", f"{total_tax:.2f}")
                            can.drawRightString(final_x, final_y, line4_value)
                        
                        if "line5_credits" in field_data:
                            line5_pos = field_data["line5_credits"]
                            final_x = line5_pos["x"] + pdf_x_offset
                            final_y = line5_pos["y"] + pdf_y_offset
                            can.setFont(line5_pos["font"], line5_pos["size"])
                            line5_value = month_data.get("line5_credits", "0.00")
                            can.drawRightString(final_x, final_y, line5_value)
                        
                        if "line6_balance" in field_data:
                            line6_pos = field_data["line6_balance"]
                            final_x = line6_pos["x"] + pdf_x_offset
                            final_y = line6_pos["y"] + pdf_y_offset
                            can.setFont(line6_pos["font"], line6_pos["size"])
                            line6_value = month_data.get("line6_balance", "0.00")
                            can.drawRightString(final_x, final_y, line6_value)
                    
                    # INDIVIDUAL PART I FIELDS - Handle standalone Part I line fields
                    elif field_name.startswith("line") and "_" in field_name:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        part_i_value = month_data.get(field_name, "0.00")
                        print(f"📊 Rendering Part I field '{field_name}' = '{part_i_value}' on page {page_num}")
                        can.drawRightString(final_x, final_y, part_i_value)
                    

                    # CATEGORY COUNT FIELDS - Handle count_a_regular, count_a_logging, etc.
                    elif field_name.startswith("count_") and ("_regular" in field_name or "_logging" in field_name):
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        count_value = month_data.get(field_name, "0")
                        # Only render if count > 0 to avoid cluttering the form
                        if count_value and count_value != "0":
                            print(f"📊 Rendering count field '{field_name}' = '{count_value}' on page {page_num}")
                            can.drawString(final_x, final_y, count_value)
                    
                    # CATEGORY AMOUNT FIELDS - Handle amount_a, amount_b, etc.
                    elif field_name.startswith("amount_") and not field_name.endswith("_regular") and not field_name.endswith("_logging"):
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        amount_value = month_data.get(field_name, "0.00")
                        # Only render if amount > 0 to avoid cluttering the form
                        if amount_value and amount_value != "0.00":
                            print(f"💰 Rendering amount field '{field_name}' = '{amount_value}' on page {page_num}")
                            can.drawRightString(final_x, final_y, amount_value)
                    
                    # PARTIAL-PERIOD TAX FIELDS - Handle tax_partial_a_regular, tax_partial_a_logging, etc.
                    elif field_name.startswith("tax_partial_") and ("_regular" in field_name or "_logging" in field_name):
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        partial_tax_value = month_data.get(field_name, "0.00")
                        # Only render if partial tax > 0 to avoid cluttering the form
                        if partial_tax_value and partial_tax_value != "0.00":
                            print(f"📊 Rendering partial tax field '{field_name}' = '{partial_tax_value}' on page {page_num}")
                            can.drawRightString(final_x, final_y, partial_tax_value)
                    
                    # CATEGORY W SUSPENDED COUNT FIELDS
                    elif field_name == "count_w_suspended_non_logging":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        count_value = month_data.get(field_name, "0")
                        if count_value and count_value != "0":
                            print(f"📊 Rendering category W non-logging count = '{count_value}' on page {page_num}")
                            can.drawString(final_x, final_y, count_value)
                    
                    elif field_name == "count_w_suspended_logging":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        count_value = month_data.get(field_name, "0")
                        if count_value and count_value != "0":
                            print(f"📊 Rendering category W logging count = '{count_value}' on page {page_num}")
                            can.drawString(final_x, final_y, count_value)
                
                can.save()
                packet.seek(0)
                
                # Create overlay page and merge with template page
                overlay_page = PdfReader(packet).pages[0]
                template_page = template.pages[page_num - 1]  # 0-indexed
                template_page.merge_page(overlay_page)
                writer.add_page(template_page)

            # Save PDF with month identifier
            out_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"form2290_{month}.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)

            # Upload PDF to S3
            pdf_key = f"{user_uid}/{month}/form2290.pdf"
            pdf_s3_upload_success = False
            try:
                with open(out_path, 'rb') as pf:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=pdf_key,
                        Body=pf,
                        ServerSideEncryption='aws:kms'
                    )
                pdf_s3_upload_success = True
            except Exception as e:
                app.logger.error("S3 PDF upload failed for month %s: %s", month, e, exc_info=True)
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="S3_UPLOAD_FAILED",
                    error_message=f"Failed to upload PDF to S3: {str(e)}",
                    endpoint="/build-pdf"
                )
                # Continue processing but note the failure

            # Update submission with PDF S3 key
            submission = db.query(Submission).get(filing_id)
            if submission:
                submission.pdf_s3_key = pdf_key
                db.commit()
            
            # Add PDF document record (only if not already exists)
            existing_pdf_doc = db.query(FilingsDocument).filter(
                FilingsDocument.filing_id == filing_id,
                FilingsDocument.document_type == 'pdf'
            ).first()
            
            if not existing_pdf_doc:
                db.add(FilingsDocument(
                    filing_id=filing_id,
                    user_uid=user_uid,
                    document_type='pdf',
                    s3_key=pdf_key,
                    uploaded_at=datetime.datetime.utcnow()
                ))
                db.commit()

            created_files.append({
                'month': month,
                'filing_id': filing_id,
                'vehicle_count': len(month_vehicles),
                'total_tax': total_tax,
                'pdf_path': out_path
            })

        print(f"✅ Form 2290 completed for {len(created_files)} different months")
        print(f"📁 Created files: {[f['month'] for f in created_files]}")
        
        # NEW LOGIC: Single file for one month, JSON response with download URLs for multiple months
        print(f"🔀 DOWNLOAD DECISION: {len(created_files)} file(s) created")
        if len(created_files) == 1:
            # Single month - return PDF directly
            print(f"📄 Returning single PDF for month {created_files[0]['month']}")
            return send_file(
                created_files[0]['pdf_path'], 
                as_attachment=True, 
                download_name=f"form2290_{created_files[0]['month']}.pdf"
            )
        else:
            # Multiple months - return JSON with download information
            print(f"� Returning JSON response with {len(created_files)} PDF download URLs")
            
            download_info = []
            for file_info in created_files:
                month = file_info['month']
                filing_id = file_info['filing_id']
                vehicle_count = file_info['vehicle_count']
                total_tax = file_info['total_tax']
                
                # Convert month code to readable format
                month_name = f"{month[:4]}-{month[4:]}"  # 202507 -> 2025-07
                
                download_info.append({
                    'month': month,
                    'month_display': month_name,
                    'filing_id': filing_id,
                    'vehicle_count': vehicle_count,
                    'total_tax': total_tax,
                    'download_url': f"/download-pdf-by-month/{month}",
                    'filename': f"form2290_{month_name}_{vehicle_count}vehicles.pdf"
                })
            
            print(f"🔄 About to return JSON response...")
            return jsonify({
                "success": True,
                "message": f"Generated {len(created_files)} separate PDFs for different months",
                "files": download_info,
                "total_files": len(created_files)
            }), 200
    
    except Exception as e:
        # Catch-all exception handler to prevent returning None
        app.logger.error("🚨 CRITICAL ERROR in build_pdf at line %d: %s", e.__traceback__.tb_lineno if e.__traceback__ else -1, e, exc_info=True)
        print(f"🚨 EXCEPTION CAUGHT: {type(e).__name__}: {str(e)}")
        if hasattr(e, '__traceback__') and e.__traceback__:
            print(f"🚨 ERROR LINE: {e.__traceback__.tb_lineno}")
        enhanced_audit.log_error_event(
            user_email=request.user.get('email', 'unknown'),
            error_type="SUBMISSION_PROCESSING_ERROR",
            error_message=f"Unexpected error during PDF submission: {str(e)}",
            endpoint="/build-pdf"
        )
        return jsonify({
            "error": "An unexpected error occurred during submission processing",
            "details": "Please try again or contact support if the issue persists"
        }), 500
    
    finally:
        db.close()

@app.route("/debug/db-info", methods=["GET"])
def debug_db_info():
    return jsonify({
        "DATABASE_URL": DATABASE_URL,
        "engine_url": str(engine.url),
        "table_names": list(Base.metadata.tables.keys())
    }), 200

@app.route("/debug/submissions", methods=["GET"])
def debug_submissions():
    db = SessionLocal()
    try:
        submissions = db.query(Submission).all()
        return jsonify({
            "count": len(submissions),
            "submissions": [
                {
                    "id": s.id,
                    "user_uid": s.user_uid,
                    "month": s.month,
                    "created_at": str(s.created_at),
                    "xml_s3_key": s.xml_s3_key,
                    "pdf_s3_key": s.pdf_s3_key
                }
                for s in submissions
            ]
        })
    finally:
        db.close()

@app.route("/debug/filings-documents", methods=["GET"])
def debug_filings_documents():
    db = SessionLocal()
    try:
        docs = db.query(FilingsDocument).all()
        return jsonify({
            "count": len(docs),
            "documents": [
                {
                    "id": d.id,
                    "filing_id": d.filing_id,
                    "user_uid": d.user_uid,
                    "document_type": d.document_type,
                    "s3_key": d.s3_key,
                    "uploaded_at": str(d.uploaded_at)
                }
                for d in docs
            ]
        })
    finally:
        db.close()

@app.route("/admin/submissions", methods=["GET"])
@verify_admin_token
def admin_view_submissions():
    """
    Admin endpoint to view all submissions with user information.
    IRS compliance: Only authorized personnel can access taxpayer data.
    """
    try:
        db = SessionLocal()
        try:
            # Simple query that was working before
            submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
            
            print(f"🔍 ADMIN DEBUG: Found {len(submissions)} total submissions in database")
            for i, s in enumerate(submissions[:5]):  # Show first 5
                print(f"  {i+1}. ID={s.id}, Month={s.month}, User={s.user_uid[:8]}..., Created={s.created_at}")
            
            submissions_list = []
            for submission in submissions:
                # Parse form_data to extract business details
                try:
                    form_data = json.loads(submission.form_data) if submission.form_data else {}
                except:
                    form_data = {}
                
                # **CALCULATE MONTH-SPECIFIC TAX** using same logic as PDF generation
                vehicles = form_data.get('vehicles', [])
                total_vehicles = len(vehicles)
                
                # Group vehicles by month for this submission
                submission_month = submission.month
                month_vehicles = [v for v in vehicles if v.get('used_month') == submission_month]
                
                # Use frontend categoryData and calculate month-specific tax (same logic as PDF generation)
                total_tax = 0
                frontend_category_data = form_data.get('categoryData', {})
                
                if frontend_category_data and month_vehicles:
                    weight_categories_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']
                    
                    for cat in weight_categories_list:
                        # Count vehicles in this month for this category
                        regular_vehicles = [v for v in month_vehicles if v.get("category") == cat and not v.get("is_logging", False)]
                        logging_vehicles = [v for v in month_vehicles if v.get("category") == cat and v.get("is_logging", False)]
                        
                        regular_count = len(regular_vehicles)
                        logging_count = len(logging_vehicles)
                        
                        if cat in frontend_category_data:
                            frontend_cat_data = frontend_category_data[cat]
                            
                            # Determine if this is annual (July) or partial-period tax
                            month_num = int(submission_month[-2:]) if submission_month and len(submission_month) >= 2 else 0
                            is_annual_month = (month_num == 7)  # July = annual tax
                            
                            if is_annual_month:
                                # Use annual tax rates for July
                                regular_per_vehicle_rate = frontend_cat_data.get('regularAnnualTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                                logging_per_vehicle_rate = frontend_cat_data.get('loggingAnnualTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                            else:
                                # Use partial-period tax rates for all other months
                                regular_per_vehicle_rate = frontend_cat_data.get('regularPartialTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                                logging_per_vehicle_rate = frontend_cat_data.get('loggingPartialTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                            
                            # Calculate month-specific totals using frontend rates
                            regular_total_tax = regular_count * regular_per_vehicle_rate
                            logging_total_tax = logging_count * logging_per_vehicle_rate
                            
                            total_category_tax = regular_total_tax + logging_total_tax
                            total_tax += total_category_tax
                    
                    print(f"🔍 ADMIN: Submission {submission.id} month-specific tax = ${total_tax:.2f}")
                
                else:
                    # Fallback: Use frontend's total tax if no categoryData available
                    frontend_part_i = form_data.get('partI', {})
                    if frontend_part_i and 'line2_tax' in frontend_part_i:
                        total_tax = float(frontend_part_i['line2_tax'])
                        print(f"🔍 ADMIN: Using frontend total tax as fallback: ${total_tax:.2f} for submission {submission.id}")
                    else:
                        # Last fallback: manual calculation for very old submissions
                        print(f"⚠️ ADMIN: No frontend data found for submission {submission.id}, using manual calculation")
                        total_tax = 0  # Will be calculated below
                    
                        # Last fallback: manual calculation for very old submissions
                        print(f"⚠️ ADMIN: No frontend data found for submission {submission.id}, using manual calculation")
                        
                        # Simple fallback calculation for old submissions
                        weight_categories = {
                            'A': 100.00, 'B': 122.00, 'C': 144.00, 'D': 166.00, 'E': 188.00, 'F': 210.00,
                            'G': 232.00, 'H': 254.00, 'I': 276.00, 'J': 298.00, 'K': 320.00, 'L': 342.00,
                            'M': 364.00, 'N': 386.00, 'O': 408.00, 'P': 430.00, 'Q': 452.00, 'R': 474.00,
                            'S': 496.00, 'T': 518.00, 'U': 540.00, 'V': 550.00, 'W': 0.00
                        }
                        
                        total_tax = 0
                        for vehicle in vehicles:
                            if vehicle.get('used_month') == submission_month:  # Only count vehicles for this month
                                category = vehicle.get('category', '')
                                if category in weight_categories:
                                    total_tax += weight_categories[category]
                
                # Simple user display - no email lookup for now
                user_display = f"User: {submission.user_uid[:8]}..." if submission.user_uid else "Unknown"
                
                submissions_list.append({
                    'id': submission.id,
                    'business_name': form_data.get('business_name', 'Unknown Business'),
                    'ein': form_data.get('ein', 'Unknown'),
                    'created_at': submission.created_at.isoformat() if submission.created_at else None,
                    'month': submission.month or 'Unknown',
                    'user_uid': submission.user_uid,
                    'user_email': user_display,  # Show partial UID for now
                    'total_vehicles': total_vehicles,
                    'total_tax': total_tax
                })
            
            log_admin_action("VIEW_ALL_SUBMISSIONS", f"Retrieved {len(submissions_list)} submissions")
            
            return jsonify({
                'submissions': submissions_list,
                'total': len(submissions_list)
            })
            
        finally:
            db.close()
            
    except Exception as e:
        log_admin_action("VIEW_ALL_SUBMISSIONS_ERROR", f"Error: {str(e)}")
        return jsonify({'error': f'Failed to retrieve submissions: {str(e)}'}), 500

@app.route("/admin/submissions/<int:submission_id>", methods=["DELETE"])
@verify_admin_token
def admin_delete_submission(submission_id):
    """
    Secure endpoint to delete test submissions and associated files.
    Includes S3 cleanup and proper audit logging.
    """
    log_admin_action("DELETE_SUBMISSION", f"Attempting to delete submission ID: {submission_id}")
    db = SessionLocal()
    try:
        # Delete related documents first
        docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
        for doc in docs:
            try:
                s3.delete_object(Bucket=BUCKET, Key=doc.s3_key)
                log_admin_action("S3_DELETE", f"Deleted S3 object: {doc.s3_key}")
            except Exception as e:
                app.logger.warning(f"Failed to delete S3 object {doc.s3_key}: {e}")
            db.delete(doc)
        
        # Delete submission
        submission = db.query(Submission).get(submission_id)
        if not submission:
            db.rollback()
            log_admin_action("DELETE_ERROR", f"Submission {submission_id} not found for deletion")
            return jsonify({"error": "Submission not found"}), 404
        
        # Delete S3 files
        if submission.xml_s3_key:
            try:
                s3.delete_object(Bucket=BUCKET, Key=submission.xml_s3_key)
                log_admin_action("S3_DELETE", f"Deleted S3 XML: {submission.xml_s3_key}")
            except Exception as e:
                app.logger.warning(f"Failed to delete S3 XML {submission.xml_s3_key}: {e}")
        
        if submission.pdf_s3_key:
            try:
                s3.delete_object(Bucket=BUCKET, Key=submission.pdf_s3_key)
                log_admin_action("S3_DELETE", f"Deleted S3 PDF: {submission.pdf_s3_key}")
            except Exception as e:
                app.logger.warning(f"Failed to delete S3 PDF {submission.pdf_s3_key}: {e}")
        
        db.delete(submission)
        db.commit()
        log_admin_action("DELETE_SUCCESS", f"Submission {submission_id} deleted from database")
        return jsonify({"message": f"Submission {submission_id} deleted successfully"}), 200
    except Exception as e:
        db.rollback()
        log_admin_action("DELETE_ERROR", f"Failed to delete submission {submission_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route("/admin/bulk-delete", methods=["POST"])
@verify_admin_token
def admin_bulk_delete():
    """
    Secure endpoint to bulk delete test submissions.
    Useful for cleaning up test data.
    """
    data = request.get_json()
    submission_ids = data.get('submission_ids', [])
    
    if not submission_ids:
        return jsonify({"error": "No submission IDs provided"}), 400
    
    log_admin_action("BULK_DELETE", f"Bulk deleting submissions: {submission_ids}")
    
    db = SessionLocal()
    try:
        deleted_count = 0
        for submission_id in submission_ids:
            # Delete documents
            docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
            for doc in docs:
                try:
                    s3.delete_object(Bucket=BUCKET, Key=doc.s3_key)
                except:
                    pass
                db.delete(doc)
            
            # Delete submission
            submission = db.query(Submission).get(submission_id)
            if submission:
                if submission.xml_s3_key:
                    try:
                        s3.delete_object(Bucket=BUCKET, Key=submission.xml_s3_key)
                    except:
                        pass
                if submission.pdf_s3_key:
                    try:
                        s3.delete_object(Bucket=BUCKET, Key=submission.pdf_s3_key)
                    except:
                        pass
                db.delete(submission)
                deleted_count += 1
        
        db.commit()
        log_admin_action("BULK_DELETE_SUCCESS", f"Successfully deleted {deleted_count} submissions")
        return jsonify({"message": f"Successfully deleted {deleted_count} submissions"}), 200
    except Exception as e:
        db.rollback()
        log_admin_action("BULK_DELETE_ERROR", f"Bulk delete failed: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route("/admin/submissions/<int:submission_id>/download/<file_type>", methods=["GET"])
@verify_admin_token
def admin_download_file(submission_id, file_type):
    """
    Secure endpoint to download PDF or XML files.
    Streams file directly from S3 with proper audit logging.
    """
    log_admin_action("DOWNLOAD_FILE", f"Downloaded {file_type.upper()} for submission ID: {submission_id}")
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).get(submission_id)
        if not submission:
            return jsonify({"error": "Submission not found"}), 404
        
        s3_key = None
        content_type = None
        
        if file_type.lower() == "pdf" and submission.pdf_s3_key:
            s3_key = submission.pdf_s3_key
            content_type = "application/pdf"
        elif file_type.lower() == "xml" and submission.xml_s3_key:
            s3_key = submission.xml_s3_key
            content_type = "application/xml"
        
        if not s3_key:
            return jsonify({"error": f"{file_type.upper()} file not found"}), 404
        
        # Download from S3 - CHANGE FILES_BUCKET to BUCKET
        try:
            response = s3.get_object(Bucket=BUCKET, Key=s3_key)  # Changed from FILES_BUCKET to BUCKET
            file_content = response['Body'].read()
            
            # Create response with proper headers
            filename = s3_key.split('/')[-1]
            response = make_response(file_content)
            response.headers['Content-Type'] = content_type
            response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
            
            return response
            
        except Exception as e:
            app.logger.error(f"Failed to download file {s3_key}: {e}")
            return jsonify({"error": f"File not accessible: {str(e)}"}), 500
    
    finally:
        db.close()

@app.route("/admin/documents/<int:doc_id>/download", methods=["GET"])
@verify_admin_token
def admin_download_document(doc_id):
    """
    Secure endpoint to download additional documents.
    """
    log_admin_action("DOWNLOAD_DOCUMENT", f"Downloaded document ID: {doc_id}")
    
    db = SessionLocal()
    try:
        document = db.query(FilingsDocument).get(doc_id)
        if not document:
            return jsonify({"error": "Document not found"}), 404
        
        if not document.s3_key:
            return jsonify({"error": "Document file not found"}), 404
        
        # Determine content type
        content_type = "application/octet-stream"
        if document.document_type.lower() == "pdf":
            content_type = "application/pdf"
        elif document.document_type.lower() == "xml":
            content_type = "application/xml"
        
        # Download from S3 - CHANGE FILES_BUCKET to BUCKET
        try:
            response = s3.get_object(Bucket=BUCKET, Key=document.s3_key)  # Changed from FILES_BUCKET to BUCKET
            file_content = response['Body'].read()
            
            # Create response with proper headers
            filename = document.s3_key.split('/')[-1]
            response = make_response(file_content)
            response.headers['Content-Type'] = content_type
            response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
            
            return response
            
        except Exception as e:
            app.logger.error(f"Failed to download document {document.s3_key}: {e}")
            return jsonify({"error": f"Document not accessible: {str(e)}"}), 500
    
    finally:
        db.close()

@app.route("/debug/s3-test", methods=["GET"])
@verify_admin_token
def debug_s3_test():
    """Test S3 connectivity and list bucket contents"""
    try:
        # Test bucket access
        response = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=10)
        
        objects = []
        if 'Contents' in response:
            for obj in response['Contents']:
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': str(obj['LastModified'])
                })
        
        return jsonify({
            "bucket": BUCKET,
            "accessible": True,
            "object_count": len(objects),
            "sample_objects": objects[:5]
        })
    except Exception as e:
        return jsonify({
            "bucket": BUCKET,
            "accessible": False,
            "error": str(e)
        }), 500

@app.route("/user/submissions", methods=["GET"])
@verify_firebase_token
def user_submissions():
    """Get all submissions for the current user"""
    user_uid = request.user['uid']
    db = SessionLocal()
    try:
        submissions = db.query(Submission).filter(
            Submission.user_uid == user_uid
        ).order_by(Submission.created_at.desc()).all()
        
        submissions_list = []
        for submission in submissions:
            # Parse form_data to get business info if available
            form_data = {}
            if submission.form_data:
                try:
                    form_data = json.loads(submission.form_data)
                except json.JSONDecodeError:
                    form_data = {}
            
            # Calculate totals from vehicles data
            vehicles = form_data.get('vehicles', [])
            total_vehicles = len(vehicles)
            
            # **USE FRONTEND'S TAX CALCULATION** - Don't recalculate, use frontend's Part I
            total_tax = 0
            frontend_part_i = form_data.get('partI', {})
            if frontend_part_i and 'line2_tax' in frontend_part_i:
                # Use the frontend's calculated tax from column 4 of Tax Computation by Category
                total_tax = float(frontend_part_i['line2_tax'])
                print(f"🔍 USER: Using frontend tax calculation: ${total_tax:.2f} for submission {submission.id}")
            else:
                # Fallback: If no frontend Part I data available (old submissions), calculate manually
                print(f"⚠️ USER: No frontend partI data found for submission {submission.id}, falling back to calculation")
                
                weight_categories = {
                    'A': 100.00, 'B': 122.00, 'C': 144.00, 'D': 166.00, 'E': 188.00, 'F': 210.00,
                    'G': 232.00, 'H': 254.00, 'I': 276.00, 'J': 298.00, 'K': 320.00, 'L': 342.00,
                    'M': 364.00, 'N': 386.00, 'O': 408.00, 'P': 430.00, 'Q': 452.00, 'R': 474.00,
                    'S': 496.00, 'T': 518.00, 'U': 540.00, 'V': 550.00, 'W': 0.00
                }
                logging_rates = {
                    'A': 75, 'B': 91.5, 'C': 108, 'D': 124.5, 'E': 141, 'F': 157.5,
                    'G': 174, 'H': 190.5, 'I': 207, 'J': 223.5, 'K': 240, 'L': 256.5,
                    'M': 273, 'N': 289.5, 'O': 306, 'P': 322.5, 'Q': 339, 'R': 355.5,
                    'S': 372, 'T': 388.5, 'U': 405, 'V': 412.5, 'W': 0
                }
                
                for vehicle in vehicles:
                    used_month = vehicle.get('used_month', '')
                    category = vehicle.get('category', '')
                    is_logging = vehicle.get('is_logging', False)
                    is_suspended = vehicle.get('is_suspended', False)
                    is_agricultural = vehicle.get('is_agricultural', False)
                    
                    if not used_month or not category:
                        continue
                    
                    # Extract month number (last 2 digits) - match frontend logic exactly
                    try:
                        month_num = int(used_month[-2:]) if used_month else 0
                    except:
                        continue
                    
                    # Use exact XML builder logic for months_left calculation
                    months_left = 12 if month_num >= 7 else (13 - month_num if 1 <= month_num <= 12 else 0)
                    
                    if months_left == 0:
                        continue
                    
                    # Get base rate - match XML builder exactly
                    if category in weight_categories:
                        base_rate = logging_rates[category] if is_logging else weight_categories[category]
                        
                        # Calculate tax using exact XML builder formula
                        vehicle_tax = round(base_rate * (months_left / 12), 2)
                        total_tax += vehicle_tax
            
            submissions_list.append({
                "id": str(submission.id),
                "business_name": form_data.get("business_name", "Unknown Business"),
                "ein": form_data.get("ein", "Unknown EIN"),
                "created_at": submission.created_at.isoformat() if submission.created_at else "",
                "month": submission.month,
                "total_vehicles": total_vehicles,
                "total_tax": round(total_tax, 2),
                "status": "Submitted",  # You can enhance this based on your business logic
                "xml_s3_key": submission.xml_s3_key,
                "pdf_s3_key": submission.pdf_s3_key
            })
        
        return jsonify({
            "count": len(submissions_list),
            "submissions": submissions_list
        })
    except Exception as e:
        app.logger.error("Error fetching user submissions: %s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch submissions"}), 500
    finally:
        db.close()

@app.route("/user/documents", methods=["GET"])
@verify_firebase_token
def user_documents():
    """Get all documents for the current user"""
    user_uid = request.user['uid']
    db = SessionLocal()
    try:
        # Query to fetch user's submissions and associated documents, but only for submissions that still exist
        rows = db.execute(
            text("""
                SELECT s.id, s.month, s.created_at, d.document_type, d.s3_key
                  FROM submissions s
                  JOIN filings_documents d ON s.id = d.filing_id
                 WHERE s.user_uid = :uid
                 ORDER BY s.created_at DESC
            """),
            {"uid": user_uid}
        ).fetchall()

        submissions = {}
        for row in rows:
            submission_id, month, created_at, doc_type, s3_key = row
            url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': BUCKET,
                    'Key': s3_key
                },
                ExpiresIn=900
            )
            if submission_id not in submissions:
                submissions[submission_id] = {
                    "id": submission_id,
                    "month": month,
                    "created_at": str(created_at),
                    "documents": []
                }
            submissions[submission_id]["documents"].append({
                "type": doc_type,
                "url": url
            })

        # Only return submissions that still exist in the submissions table
        # (The above query already does this, but if you ever soft-delete, filter here)
        return jsonify({
            "count": len(submissions),
            "submissions": list(submissions.values())
        })
    except Exception as e:
        app.logger.error("Error fetching user documents: %s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch documents"}), 500
    finally:
        db.close()

@app.route("/user/submissions/<submission_id>/download/<file_type>", methods=["GET"])
@verify_firebase_token
def download_submission_file(submission_id, file_type):
    """Download PDF or XML file for a specific submission"""
    user_uid = request.user['uid']
    
    if file_type not in ['pdf', 'xml']:
        return jsonify({"error": "Invalid file type. Must be 'pdf' or 'xml'"}), 400
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(
            Submission.id == submission_id,
            Submission.user_uid == user_uid
        ).first()
        
        if not submission:
            return jsonify({"error": "Submission not found"}), 404
        
        # Get the appropriate S3 key
        s3_key = submission.pdf_s3_key if file_type == 'pdf' else submission.xml_s3_key
        
        if not s3_key:
            return jsonify({"error": f"{file_type.upper()} file not found for this submission"}), 404
        
        # Generate presigned URL for download
        try:
            url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': BUCKET,
                    'Key': s3_key
                },
                ExpiresIn=3600  # 1 hour
            )
            
            # Fetch the file from S3 and return it as a download
            response = s3.get_object(Bucket=BUCKET, Key=s3_key)
            file_content = response['Body'].read()
            
            # Set appropriate content type and headers
            content_type = 'application/pdf' if file_type == 'pdf' else 'application/xml'
            filename = f"form2290-{submission_id}.{file_type}"
            
            return Response(
                file_content,
                mimetype=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename={filename}',
                    'Content-Type': content_type
                }
            )
            
        except s3.exceptions.NoSuchKey:
            return jsonify({"error": f"File not found in storage"}), 404
        except Exception as e:
            app.logger.error(f"S3 download error: {e}")
            return jsonify({"error": "Download failed"}), 500
    
    except Exception as e:
        app.logger.error("Error downloading submission file: %s", e, exc_info=True)
        return jsonify({"error": "Failed to download file"}), 500
    finally:
        db.close()

@app.route("/download-pdf-by-month/<month>", methods=["GET"])
@verify_firebase_token
def download_pdf_by_month(month):
    """Download PDF for a specific month"""
    user_uid = request.user['uid']
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(
            Submission.user_uid == user_uid,
            Submission.month == month
        ).order_by(Submission.created_at.desc()).first()
        
        if not submission or not submission.pdf_s3_key:
            return jsonify({"error": f"PDF not found for month {month}"}), 404
        
        # Generate presigned URL for download
        try:
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET, 'Key': submission.pdf_s3_key},
                ExpiresIn=300
            )
            return jsonify({"download_url": url}), 200
        except Exception as e:
            app.logger.error("Failed to generate presigned URL: %s", e)
            return jsonify({"error": "Failed to generate download link"}), 500
    
    finally:
        db.close()

@app.route("/test-connection", methods=["GET", "POST", "OPTIONS"])
def test_connection():
    """Test endpoint to verify connection"""
    if request.method == "OPTIONS":
        return make_response(jsonify({}), 200)
    
    return jsonify({
        "status": "success",
        "message": "Backend is connected and working!",
        "method": request.method,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200

@app.route("/admin/audit-logs", methods=["GET"])
@verify_admin_token
def download_audit_logs():
    """Download audit logs for compliance reporting"""
    try:
        with open('audit.log', 'r') as f:
            logs = f.read()
        
        response = make_response(logs)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = 'attachment; filename=audit.log'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# POSITION TUNER API ENDPOINTS
# ============================================

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get current form field positions"""
    try:
        positions_file = os.path.join(os.path.dirname(__file__), "form_positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                positions = json.load(f)
            return jsonify(positions)
        else:
            return jsonify({"error": "Positions file not found"}), 404
    except Exception as e:
        audit_logger.error(f"get_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions', methods=['POST'])
def update_positions():
    """Update form field positions"""
    global FORM_POSITIONS
    try:
        positions = request.get_json()
        if not positions:
            return jsonify({"error": "No position data provided"}), 400
        
        positions_file = os.path.join(os.path.dirname(__file__), "form_positions.json")
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        
        # Reload the global FORM_POSITIONS to use updated positions immediately
        FORM_POSITIONS = load_form_positions()
        
        audit_logger.info(f"update_positions: Positions updated and reloaded successfully")
        return jsonify({"message": "Positions updated and reloaded successfully"})
    except Exception as e:
        audit_logger.error(f"update_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions/reload', methods=['POST'])
def reload_positions():
    """Reload form field positions from file"""
    global FORM_POSITIONS
    try:
        FORM_POSITIONS = load_form_positions()
        audit_logger.info("reload_positions: Positions reloaded successfully")
        return jsonify({"message": "Positions reloaded successfully", "positions": FORM_POSITIONS})
    except Exception as e:
        audit_logger.error(f"reload_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for position tuner"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()})

# ============================================
# ENHANCED POSITION TUNER API ENDPOINTS WITH OFFSET SUPPORT
# ============================================

@app.route('/api/positions/update-offset', methods=['POST'])
def update_position_offset():
    """Update PDF offset values for a specific field"""
    try:
        data = request.get_json()
        field_name = data.get('field_name')
        x_offset = data.get('x_offset', 0)
        y_offset = data.get('y_offset', 0)
        
        if not field_name:
            return jsonify({"error": "field_name is required"}), 400
        
        # Load current positions
        positions_file = os.path.join(os.path.dirname(__file__), "form_positions.json")
        with open(positions_file, 'r') as f:
            positions = json.load(f)
        
        if field_name not in positions:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        # Update offset values
        positions[field_name]["pdf_x_offset"] = int(x_offset)
        positions[field_name]["pdf_y_offset"] = int(y_offset)
        
        # Save updated positions
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        
        # Reload positions in memory
        global FORM_POSITIONS
        FORM_POSITIONS = positions
        
        return jsonify({
            "success": True,
            "message": f"Updated PDF offsets for {field_name}",
            "field": field_name,
            "pdf_x_offset": x_offset,
            "pdf_y_offset": y_offset,
            "final_pdf_x": positions[field_name]["x"] + x_offset,
            "final_pdf_y": positions[field_name]["y"] + y_offset
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions/test-pdf', methods=['POST'])
def test_pdf_with_offsets():
    """Generate a test PDF with sample data using current offset settings for all pages"""
    print("=== TEST PDF GENERATION STARTED ===")
    try:
        # Sample test data with comprehensive field coverage
        test_data = {
            "business_name": "TEST COMPANY LLC",
            "address": "123 Test Street",
            "city": "Test City",
            "state": "TX",
            "zip": "12345",
            "ein": "123456789",
            "tax_year": "2025",
            "used_on_july": "202507",
            "address_change": True,
            "vin_correction": True,  # Changed to True to show this checkbox
            "amended_return": True,  # Changed to True to show this checkbox
            "final_return": True,   # Changed to True to show this checkbox
            "has_disposals": True,   # Added this field
            "consent_to_disclose": True,  # Added this field
            "preparer_self_employed": True,  # Added this field
            "payEFTPS": True,  # Added this field
            "payCard": True,  # Changed to True to show this checkbox
            
            # Officer information
            "officer_name": "John Smith",
            "officer_title": "President",
            "printed_name": "John Smith",
            "signature": "John Smith",
            "signature_date": "2025-07-05",
            "taxpayer_phone": "5551234567",

            # Preparer information
            "preparer_name": "Jane Preparer",
            "preparer_ptin": "P12345678",
            "date_prepared": "2025-07-05",
            "preparer_firm_name": "Tax Prep LLC",
            "preparer_firm_ein": "987654321",
            "preparer_firm_address": "456 Tax Street",
            "preparer_firm_citystatezip": "Tax City, TX 67890",
            "preparer_firm_phone": "5559876543",
            
            # Designee information
            "designee_name": "Bob Designee",
            "designee_phone": "5555551234",
            "designee_pin": "54321",
            
            # Explanation fields
            "reasonable_cause_explanation": "Test explanation for amended return filing.",
            
            # Page 2 fields - Count fields (vehicle counts by category)
            "count_a_logging": "5",
            "count_a_regular": "3",
            "count_b_logging": "2", 
            "count_b_regular": "7",
            "count_c_logging": "1",
            "count_c_regular": "4",
            "count_d_logging": "6",
            "count_d_regular": "2",
            "count_e_logging": "3",
            "count_e_regular": "8",
            "count_f_logging": "1",
            "count_f_regular": "5",
            "count_g_logging": "2",
            "count_g_regular": "3",
            "count_h_logging": "4",
            "count_h_regular": "1",
            "count_i_logging": "7",
            "count_i_regular": "2",
            "count_j_logging": "1",
            "count_j_regular": "6",
            "count_k_logging": "3",
            "count_k_regular": "4",
            "count_l_logging": "2",
            "count_l_regular": "5",
            "count_m_logging": "1",
            "count_m_regular": "3",
            "count_n_logging": "4",
            "count_n_regular": "2",
            "count_o_logging": "1",
            "count_o_regular": "7",
            "count_p_logging": "2",
            "count_p_regular": "1",
            "count_q_logging": "3",
            "count_q_regular": "2",
            "count_r_logging": "1",
            "count_r_regular": "4",
            "count_s_logging": "2",
            "count_s_regular": "3",
            "count_t_logging": "1",
            "count_t_regular": "2",
            "count_u_logging": "3",
            "count_u_regular": "1",
            "count_v_logging": "2",
            "count_v_regular": "4",
            "count_w_suspended_logging": "1",
            "count_w_suspended_non_logging": "2",
            
            # Amount fields (tax amounts by category)
            "amount_a": "1250.00",
            "amount_b": "875.00",
            "amount_c": "650.00",
            "amount_d": "1100.00",
            "amount_e": "950.00",
            "amount_f": "750.00",
            "amount_g": "825.00",
            "amount_h": "425.00",
            "amount_i": "1375.00",
            "amount_j": "625.00",
            "amount_k": "1050.00",
            "amount_l": "800.00",
            "amount_m": "500.00",
            "amount_n": "725.00",
            "amount_o": "1200.00",
            "amount_p": "350.00",
            "amount_q": "675.00",
            "amount_r": "925.00",
            "amount_s": "775.00",
            "amount_t": "525.00",
            "amount_u": "850.00",
            "amount_v": "1150.00",
            "amount_w_suspended": "275.00",
            
            # Tax partial fields (partial period tax calculations)
            "tax_partial_a_logging": "125.50",
            "tax_partial_a_regular": "87.25",
            "tax_partial_b_logging": "95.75",
            "tax_partial_b_regular": "142.00",
            "tax_partial_c_logging": "68.50",
            "tax_partial_c_regular": "110.25",
            "tax_partial_d_logging": "156.75",
            "tax_partial_d_regular": "73.50",
            "tax_partial_e_logging": "89.25",
            "tax_partial_e_regular": "167.00",
            "tax_partial_f_logging": "45.75",
            "tax_partial_f_regular": "98.50",
            "tax_partial_g_logging": "112.25",
            "tax_partial_g_regular": "76.75",
            "tax_partial_h_logging": "134.50",
            "tax_partial_h_regular": "52.25",
            "tax_partial_i_logging": "178.75",
            "tax_partial_i_regular": "91.50",
            "tax_partial_j_logging": "64.25",
            "tax_partial_j_regular": "123.75",
            "tax_partial_k_logging": "145.50",
            "tax_partial_k_regular": "82.25",
            "tax_partial_l_logging": "67.75",
            "tax_partial_l_regular": "129.50",
            "tax_partial_m_logging": "58.25",
            "tax_partial_m_regular": "104.75",
            "tax_partial_n_logging": "116.50",
            "tax_partial_n_regular": "71.25",
            "tax_partial_o_logging": "93.75",
            "tax_partial_o_regular": "158.50",
            "tax_partial_p_logging": "79.25",
            "tax_partial_p_regular": "42.75",
            "tax_partial_q_logging": "127.50",
            "tax_partial_q_regular": "85.25",
            "tax_partial_r_logging": "61.75",
            "tax_partial_r_regular": "139.50",
            "tax_partial_s_logging": "103.25",
            "tax_partial_s_regular": "74.75",
            "tax_partial_t_logging": "88.50",
            "tax_partial_t_regular": "151.25",
            "tax_partial_u_logging": "96.75",
            "tax_partial_u_regular": "69.50",
            "tax_partial_v_logging": "121.25",
            "tax_partial_v_regular": "84.75",
            
            # Part I Tax Summary fields - Now using frontend calculated values
            "line2_tax": "15750.50", 
            "line3_increase": "0.00",
            "line4_total": "15750.50",
            "line5_credits": "250.00",
            "line6_balance": "15500.50",
            "total_logging_vehicles": "55",
            "total_regular_vehicles": "72",
            
            "vehicles": [
                {
                    "vin": "1HGBH41JXMN109186",
                    "category": "A",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "2HGBH41JXMN109187",
                    "category": "W",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": True
                },
                {
                    "vin": "3HGBH41JXMN109188",
                    "category": "W",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": True,
                    "is_agricultural": False
                },
                {
                    "vin": "4HGBH41JXMN109189",
                    "category": "B",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "5HGBH41JXMN109190",
                    "category": "C",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "6HGBH41JXMN109191",
                    "category": "D",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "7HGBH41JXMN109192",
                    "category": "E",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "8HGBH41JXMN109193",
                    "category": "F",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "9HGBH41JXMN109194",
                    "category": "G",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1AHGBH41JXMN10919",
                    "category": "H",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1BHGBH41JXMN10919",
                    "category": "I",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1CHGBH41JXMN10919",
                    "category": "J",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1DHGBH41JXMN10919",
                    "category": "K",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1EHGBH41JXMN10919",
                    "category": "L",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1FHGBH41JXMN10919",
                    "category": "M",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1GHGBH41JXMN10919",
                    "category": "N",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1HHGBH41JXMN10919",
                    "category": "O",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1IHGBH41JXMN10919",
                    "category": "P",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1JHGBH41JXMN10919",
                    "category": "Q",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1KHGBH41JXMN10919",
                    "category": "R",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1LHGBH41JXMN10919",
                    "category": "S",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1MHGBH41JXMN10919",
                    "category": "T",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1NHGBH41JXMN10919",
                    "category": "U",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "1OHGBH41JXMN10919",
                    "category": "V",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                }
            ]
        }
        
        # Calculate vehicle statistics
        vehicles = test_data.get("vehicles", [])
        total_reported = len(vehicles)
        total_suspended = len([v for v in vehicles if v.get("category") == "W"])
        total_taxable = total_reported - total_suspended
        
        # Add calculated statistics to test data
        test_data["total_reported_vehicles"] = str(total_reported)
        test_data["total_suspended_vehicles"] = str(total_suspended) 
        test_data["total_taxable_vehicles"] = str(total_taxable)
        
        # Add dynamic VIN fields to test data
        for i, vehicle in enumerate(vehicles, 1):
            if i <= 24:  # Support up to 24 VINs as defined in positions
                test_data[f"vin_{i}"] = vehicle.get("vin", "")
                test_data[f"vin_{i}_category"] = vehicle.get("category", "")
        
        # Load template
        template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
        print(f"Loading template from: {template_path}")
        if not os.path.exists(template_path):
            print("ERROR: Template not found!")
            return jsonify({"error": "Template not found"}), 500
            
            
        template = PdfReader(open(template_path, "rb"), strict=False)
        print(f"Template loaded successfully with {len(template.pages)} pages")
        writer = PdfWriter()
        
        # Process each page in the template
        for page_num in range(1, len(template.pages) + 1):
            
            # Create overlay for this page
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            
            # Get all fields that should appear on this page
            fields_on_page = []
            for field_name, field_data in FORM_POSITIONS.items():
                # Skip special field types that don't have pages array
                if "x" not in field_data or "y" not in field_data:
                    continue
                    
                # Handle both old single page format and new pages array format
                field_pages = []
                if "pages" in field_data and isinstance(field_data["pages"], list):
                    field_pages = field_data["pages"]
                elif "page" in field_data:
                    field_pages = [field_data["page"]]
                else:
                    field_pages = [1]  # Default to page 1
                
                if page_num in field_pages:
                    fields_on_page.append(field_name)
            
            # Calculate conditional checkboxes visibility for test data
            has_agricultural = any(v.get("is_agricultural", False) for v in test_data["vehicles"])
            has_suspended = any(v.get("is_suspended", False) and not v.get("is_agricultural", False) for v in test_data["vehicles"])
            has_non_agricultural = any(not v.get("is_agricultural", False) and not v.get("is_suspended", False) for v in test_data["vehicles"])
            
            # Render fields for this page
            for field_name in fields_on_page:
                field_data = FORM_POSITIONS[field_name]
                
                # Skip fields that don't have x,y coordinates (special field types)
                if "x" not in field_data or "y" not in field_data:
                    continue
                
                # Skip conditional checkboxes that shouldn't be rendered based on vehicle data
                if field_name == "checkbox_agricultural" and not has_agricultural:
                    continue
                elif field_name == "checkbox_suspended" and not has_suspended:
                    continue
                elif field_name == "checkbox_non_agricultural" and not has_non_agricultural:
                    continue
                
                # Get position for this specific page (handle page-specific positions)
                pos_x = field_data["x"]
                pos_y = field_data["y"] 
                x_positions = field_data.get("x_positions")
                
                # Check for page-specific position overrides
                if "pagePositions" in field_data and str(page_num) in field_data["pagePositions"]:
                    page_override = field_data["pagePositions"][str(page_num)]
                    if "x" in page_override:
                        pos_x = page_override["x"]
                    if "y" in page_override:
                        pos_y = page_override["y"]
                    if "x_positions" in page_override:
                        x_positions = page_override["x_positions"]
                
                # Apply offsets
                pdf_x_offset = field_data.get("pdf_x_offset", 0)
                pdf_y_offset = field_data.get("pdf_y_offset", 0)
                
                can.setFont(field_data["font"], field_data["size"])
                
                # Render based on field type
                try:
                    if field_name == "tax_year":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["tax_year"])
                        
                    elif field_name == "business_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["business_name"])
                        
                    elif field_name == "address":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["address"])
                        
                    elif field_name == "city_state_zip":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        city_state_zip = f"{test_data['city']}, {test_data['state']} {test_data['zip']}"
                        can.drawString(final_x, final_y, city_state_zip)
                        
                    elif field_name == "used_on_july" and x_positions:
                        used_on_july = test_data["used_on_july"]
                        for i, digit in enumerate(used_on_july):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, digit)
                        
                    elif field_name == "used_on_july":
                        # Fallback for when x_positions is not available
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["used_on_july"])
                        
                    elif field_name == "officer_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["officer_name"])
                        
                    elif field_name == "officer_title":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["officer_title"])
                        
                    elif field_name == "printed_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["printed_name"])
                        
                    elif field_name == "signature":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["signature"])
                        
                    elif field_name == "signature_date":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["signature_date"])
                        
                    elif field_name == "taxpayer_phone":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["taxpayer_phone"])
                        

                    elif field_name == "preparer_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_name"])
                        
                    elif field_name == "preparer_ptin":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_ptin"])
                        
                    elif field_name == "date_prepared":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["date_prepared"])
                        
                    elif field_name == "preparer_firm_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_firm_name"])
                        
                    elif field_name == "preparer_firm_ein":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_firm_ein"])
                        
                    elif field_name == "preparer_firm_address":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_firm_address"])
                        
                    elif field_name == "preparer_firm_citystatezip":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_firm_citystatezip"])
                        
                    elif field_name == "preparer_firm_phone":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["preparer_firm_phone"])
                        
                    elif field_name == "designee_name":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["designee_name"])
                        
                    elif field_name == "designee_phone":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["designee_phone"])
                        
                    elif field_name == "designee_pin":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["designee_pin"])
                        
                    elif field_name == "reasonable_cause_explanation":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data["reasonable_cause_explanation"])
                        
                    elif field_name == "ein_digits" and x_positions:
                        ein = test_data["ein"]
                        for i, digit in enumerate(ein):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, digit)
                    
                    elif field_name.startswith("vin_") and not field_name.endswith("_category") and x_positions:
                        # Handle VIN fields with character-by-character spacing
                        vin_value = test_data.get(field_name, "")
                        for i, char in enumerate(vin_value):
                            if i < len(x_positions):
                                final_x = x_positions[i] + pdf_x_offset
                                final_y = pos_y + pdf_y_offset
                                can.drawString(final_x, final_y, char)
                    
                    elif field_name.startswith("checkbox_"):
                        # Test checkboxes
                        should_check = False
                        if field_name == "checkbox_address_change":
                            should_check = test_data.get("address_change", False)
                        elif field_name == "checkbox_vin_correction":
                            should_check = test_data.get("vin_correction", False)
                        elif field_name == "checkbox_amended_return":
                            should_check = test_data.get("amended_return", False)
                        elif field_name == "checkbox_final_return":
                            should_check = test_data.get("final_return", False)
                        elif field_name == "checkbox_has_disposals":
                            should_check = test_data.get("has_disposals", False)
                        elif field_name == "checkbox_consent_to_disclose":
                            should_check = test_data.get("consent_to_disclose", False)
                        elif field_name == "checkbox_preparer_self_employed":
                            should_check = test_data.get("preparer_self_employed", False)
                        elif field_name == "checkbox_payEFTPS":
                            should_check = test_data.get("payEFTPS", False)
                        elif field_name == "checkbox_payCard":
                            should_check = test_data.get("payCard", False)
                        elif field_name == "checkbox_agricultural":
                            should_check = has_agricultural  # Show checkbox if there are agricultural vehicles
                        elif field_name == "checkbox_suspended":
                            should_check = has_suspended  # Show checkbox if there are suspended vehicles
                        elif field_name == "checkbox_non_agricultural":
                            should_check = has_non_agricultural  # Show checkbox if there are non-agricultural vehicles
                        
                        if should_check:
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                    
                    # NEW VEHICLE STATISTICS FIELDS
                    elif field_name == "total_reported_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data.get("total_reported_vehicles", ""))
                        
                    elif field_name == "total_suspended_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data.get("total_suspended_vehicles", ""))
                        
                    elif field_name == "total_taxable_vehicles":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data.get("total_taxable_vehicles", ""))
                    
                    # DYNAMIC VIN FIELDS
                    elif field_name.startswith("vin_") and not field_name.endswith("_category"):
                        # Handle VIN fields (vin_1, vin_2, etc.)
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        vin_value = test_data.get(field_name, "")
                        if vin_value:  # Only render if VIN exists
                            can.drawString(final_x, final_y, vin_value)
                            
                    elif field_name.startswith("vin_") and field_name.endswith("_category"):
                        # Handle VIN category fields (vin_1_category, vin_2_category, etc.)
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        category_value = test_data.get(field_name, "")
                        if category_value:  # Only render if category exists
                            can.drawString(final_x, final_y, category_value)
                    
                    # PAGE 2 FIELDS - Count fields (vehicle counts by category)
                    elif field_name.startswith("count_") and field_name in test_data:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data[field_name])
                    
                    # PAGE 2 FIELDS - Amount fields (tax amounts by category)
                    elif field_name.startswith("amount_") and field_name in test_data:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data[field_name])
                    
                    # PAGE 2 FIELDS - Tax partial fields (partial period tax calculations)
                    elif field_name.startswith("tax_partial_") and field_name in test_data:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data[field_name])
                    

                    # TAX SUMMARY LINE FIELDS
                    elif field_name.startswith("line") and field_name in test_data:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data[field_name])
                    
                    # TOTAL VEHICLE COUNT FIELDS
                    elif field_name.startswith("total_") and "vehicles" in field_name and field_name in test_data:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, test_data[field_name])
                    
                    else:
                        # Generic field rendering with placeholder text
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        placeholder_text = f"[{field_name.replace('_', ' ').title()}]"
                        can.drawString(final_x, final_y, placeholder_text)
                
                except Exception as field_error:
                    print(f"Error processing field {field_name}: {str(field_error)}")
                    raise field_error
            
            can.save()
            packet.seek(0)
            
            # Get template page first
            template_page = template.pages[page_num - 1]  # 0-indexed
            
            # Create overlay page and merge with template page only if there are fields
            if fields_on_page:
                overlay_page = PdfReader(packet).pages[0]
                template_page.merge_page(overlay_page)
            
            writer.add_page(template_page)
        
        # Create in-memory PDF buffer for direct response
        buffer = io.BytesIO()
        writer.write(buffer)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Generate timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create response with proper headers for reliable download (no server save)
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="offset_test_{timestamp}.pdf"'
        response.headers['Content-Length'] = len(pdf_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        print(f"Error generating test PDF: {str(e)}")
        return jsonify({"error": f"Failed to generate test PDF: {str(e)}"}), 500

@app.route('/api/positions/get-field-info/<field_name>', methods=['GET'])
def get_field_info(field_name):
    """Get detailed information about a specific field including offsets"""
    try:
        if field_name not in FORM_POSITIONS:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        field_data = FORM_POSITIONS[field_name]
        return jsonify({
            "field_name": field_name,
            "live_position": {
                "x": field_data["x"],
                "y": field_data["y"]
            },
            "pdf_offsets": {
                "x_offset": field_data.get("pdf_x_offset", 0),
                "y_offset": field_data.get("pdf_y_offset", 0)
            },
            "final_pdf_position": {
                "x": field_data["x"] + field_data.get("pdf_x_offset", 0),
                "y": field_data["y"] + field_data.get("pdf_y_offset", 0)
            },
            "font": field_data["font"],
            "size": field_data["size"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions/reset-offset/<field_name>', methods=['POST'])
def reset_field_offset(field_name):
    """Reset PDF offsets for a specific field to zero"""
    try:
        positions_file = os.path.join(os.path.dirname(__file__), "form_positions.json")
        with open(positions_file, 'r') as f:
            positions = json.load(f)
        
        if field_name not in positions:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        # Reset offsets to zero
        positions[field_name]["pdf_x_offset"] = 0
        positions[field_name]["pdf_y_offset"] = 0
        
        # Save updated positions
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        
        # Reload positions in memory
        global FORM_POSITIONS
        FORM_POSITIONS = positions
        
        return jsonify({
            "success": True,
            "message": f"Reset PDF offsets for {field_name}",
            "field": field_name,
            "pdf_x_offset": 0,
            "pdf_y_offset": 0
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🔥 Starting Flask development server...")
    print(f"🔧 Flask ENV: {os.getenv('FLASK_ENV', 'development')}")
    print(f"🗄️  Database: {DATABASE_URL[:50]}...")
    
    # Test database connection
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
    
    print(f"🪣 S3 Bucket: {BUCKET}")
    print(f"👨‍💼 Admin Email: {os.getenv('ADMIN_EMAIL', 'Not Set')}")
    
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
