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

# Initialize the enhanced logger
irs_audit = IRS2290AuditLogger()

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
        
        # ADD THIS - Log user submission
        try:
            irs_audit.log_user_action(
                user_id=request.user['uid'],
                action='FORM_SUBMISSION',
                form_data=data,
                ein=data.get('ein'),
                tax_year=data.get('tax_year', '2025')
            )
        except Exception as e:
            app.logger.error(f"Enhanced audit logging failed: {e}")
    
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
    
    # Group vehicles by month - FIX: use 'used_month' not 'used_in_month'
    vehicles = data.get('vehicles', [])
    vehicles_by_month = {}
    
    print(f"🔍 DEBUGGING: Total vehicles received: {len(vehicles)}")
    for idx, vehicle in enumerate(vehicles):
        month = vehicle.get('used_month', data.get('used_on_july', ''))
        print(f"🚗 Vehicle {idx+1}: VIN={vehicle.get('vin', 'N/A')[:8]}..., used_month='{month}'")
        if month not in vehicles_by_month:
            vehicles_by_month[month] = []
        vehicles_by_month[month].append(vehicle)
    
    print(f"📅 GROUPING RESULT: {len(vehicles_by_month)} different months found:")
    for month, month_vehicles in vehicles_by_month.items():
        print(f"  - Month {month}: {len(month_vehicles)} vehicles")
    
    if not vehicles_by_month:
        return jsonify({"error": "No vehicles found"}), 400

    print(f"🚗 Vehicles grouped by month: {vehicles_by_month}")
    print(f"🔢 Number of different months: {len(vehicles_by_month)}")

    created_files = []
    
    db = SessionLocal()
    try:
        template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
        if not os.path.exists(template_path):
            return jsonify({"error": "Template not found"}), 500
            
        template = PdfReader(open(template_path, "rb"), strict=False)
        
        # Process each month separately
        for month, month_vehicles in vehicles_by_month.items():
            print(f"📅 Processing month {month} with {len(month_vehicles)} vehicles")
            
            # Calculate totals for this month using same logic as XML builder
            total_tax = 0.0
            weight_categories = {
                'A': 100.00, 'B': 122.00, 'C': 144.00, 'D': 166.00, 'E': 188.00, 'F': 210.00,
                'G': 232.00, 'H': 254.00, 'I': 276.00, 'J': 298.00, 'K': 320.00, 'L': 342.00,
                'M': 364.00, 'N': 386.00, 'O': 408.00, 'P': 430.00, 'Q': 452.00, 'R': 474.00,
                'S': 496.00, 'T': 518.00, 'U': 540.00, 'V': 550.00, 'W': 0.00
            }
            logging_rates = {
                'A': 75.0, 'B': 91.5, 'C': 108.0, 'D': 124.5, 'E': 141.0, 'F': 157.5,
                'G': 174.0, 'H': 190.5, 'I': 207.0, 'J': 223.5, 'K': 240.0, 'L': 256.5,
                'M': 273.0, 'N': 289.5, 'O': 306.0, 'P': 322.5, 'Q': 339.0, 'R': 355.5,
                'S': 372.0, 'T': 388.5, 'U': 405.0, 'V': 412.5, 'W': 0.0
            }
            
            for vehicle in month_vehicles:
                used_month = vehicle.get('used_month', '')
                category = vehicle.get('category', '')
                is_logging = vehicle.get('is_logging', False)
                is_suspended = vehicle.get('is_suspended', False)
                is_agricultural = vehicle.get('is_agricultural', False)
                
                if not used_month or not category or is_suspended or is_agricultural:
                    continue
                
                # Extract month number (last 2 digits) - match XML builder logic exactly
                try:
                    month_num = int(used_month[-2:]) if used_month.isdigit() else 0
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
            
            print(f"💰 Total tax for month {month}: ${total_tax:.2f}")
            
            # Always create a new submission (remove the update logic)
            print(f"✨ Creating new submission for month {month}")
            
            # Create form data for this month
            month_data = data.copy()
            month_data['vehicles'] = month_vehicles
            month_data['used_on_july'] = month
            
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

            # Create submission record
            submission = Submission(
                user_uid=user_uid,
                month=month,
                xml_s3_key=xml_key,
                form_data=json.dumps(month_data)
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
                        
                    elif field_name == "tax_credits":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        credits = float(data.get("tax_credits", 0))
                        can.drawRightString(final_x, final_y, f"{credits:.2f}")
                    
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
                        
                    elif field_name == "preparer_phone":
                        if data.get("include_preparer", False):
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, data.get("preparer_phone", ""))
                        
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
                        
                    elif field_name == "used_on_july":
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, data.get("used_on_july", ""))
                    
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
                        
                        if should_check:
                            final_x = pos_x + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, "X")
                    
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
                        # Handle tax calculation lines
                        if "line1_vehicles" in field_data:
                            line1_pos = field_data["line1_vehicles"]
                            final_x = line1_pos["x"] + pdf_x_offset
                            final_y = line1_pos["y"] + pdf_y_offset
                            can.setFont(line1_pos["font"], line1_pos["size"])
                            can.drawRightString(final_x, final_y, str(len(month_vehicles)))
                        
                        if "line2_tax" in field_data:
                            line2_pos = field_data["line2_tax"]
                            final_x = line2_pos["x"] + pdf_x_offset
                            final_y = line2_pos["y"] + pdf_y_offset
                            can.setFont(line2_pos["font"], line2_pos["size"])
                            can.drawRightString(final_x, final_y, f"{total_tax:.2f}")
                        
                        if "line3_increase" in field_data:
                            line3_pos = field_data["line3_increase"]
                            final_x = line3_pos["x"] + pdf_x_offset
                            final_y = line3_pos["y"] + pdf_y_offset
                            can.setFont(line3_pos["font"], line3_pos["size"])
                            can.drawRightString(final_x, final_y, "0.00")
                        
                        if "line4_total" in field_data:
                            line4_pos = field_data["line4_total"]
                            final_x = line4_pos["x"] + pdf_x_offset
                            final_y = line4_pos["y"] + pdf_y_offset
                            can.setFont(line4_pos["font"], line4_pos["size"])
                            can.drawRightString(final_x, final_y, f"{total_tax:.2f}")
                        
                        if "line5_credits" in field_data:
                            line5_pos = field_data["line5_credits"]
                            final_x = line5_pos["x"] + pdf_x_offset
                            final_y = line5_pos["y"] + pdf_y_offset
                            can.setFont(line5_pos["font"], line5_pos["size"])
                            credits = float(data.get("tax_credits", 0))
                            can.drawRightString(final_x, final_y, f"{credits:.2f}")
                        
                        if "line6_balance" in field_data:
                            line6_pos = field_data["line6_balance"]
                            final_x = line6_pos["x"] + pdf_x_offset
                            final_y = line6_pos["y"] + pdf_y_offset
                            can.setFont(line6_pos["font"], line6_pos["size"])
                            credits = float(data.get("tax_credits", 0))
                            balance_due = max(0, total_tax - credits)
                            can.drawRightString(final_x, final_y, f"{balance_due:.2f}")
                
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
            try:
                with open(out_path, 'rb') as pf:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=pdf_key,
                        Body=pf,
                        ServerSideEncryption='aws:kms'
                    )
            except Exception as e:
                app.logger.error("S3 PDF upload failed for month %s: %s", month, e, exc_info=True)

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
            
            return jsonify({
                "success": True,
                "message": f"Generated {len(created_files)} separate PDFs for different months",
                "files": download_info,
                "total_files": len(created_files)
            }), 200
    
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
                
                # Calculate totals from vehicles
                vehicles = form_data.get('vehicles', [])
                total_vehicles = len(vehicles)
                
                # Calculate tax using the same logic as frontend
                total_tax = 0
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
                    
                    if not used_month or not category or is_suspended or is_agricultural:
                        continue
                    
                    # Extract month number (last 2 digits) - match XML builder logic exactly
                    try:
                        month_num = int(used_month[-2:]) if used_month.isdigit() else 0
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
            
            # Calculate totals from vehicles data (same logic as admin endpoint)
            vehicles = form_data.get('vehicles', [])
            total_vehicles = len(vehicles)
            
            # Calculate tax using the same logic as admin endpoint
            total_tax = 0
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
                
                if not used_month or not category or is_suspended or is_agricultural:
                    continue
                
                # Extract month number (last 2 digits) - match XML builder logic exactly
                try:
                    month_num = int(used_month[-2:]) if used_month.isdigit() else 0
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

@app.route('/api/generate-test-pdf', methods=['POST'])
def generate_test_pdf():
    """Generate a test PDF with current positions for validation using the actual Form 2290 template"""
    try:
        # Get test data from request
        test_data = request.get_json()
        
        # Use current form positions
        positions = FORM_POSITIONS
        
        audit_logger.info("generate_test_pdf: Generating test PDF with current positions using actual template")
        
        # Load the actual Form 2290 template
        template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
        if not os.path.exists(template_path):
            return jsonify({"error": "Form template not found"}), 404
            
        try:
            template = PdfReader(open(template_path, "rb"), strict=False)
        except Exception as e:
            return jsonify({"error": f"Could not read template: {str(e)}"}), 500

        writer = PdfWriter()
        overlays = []

        # Process each page of the template
        for pg_idx in range(len(template.pages)):
            if pg_idx == 0:  # Only overlay on first page
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                
                # === BUSINESS INFORMATION SECTION ===
                
                # Set text color to BLACK to ensure visibility
                can.setFillColorRGB(0, 0, 0)  # Black text
                
                # Business Name
                if 'business_name' in positions and 'business_name' in test_data:
                    pos = positions['business_name']
                    can.setFont(pos.get('font', 'Helvetica'), pos.get('size', 10))
                    # Use coordinates directly (frontend coordinates are already in PDF coordinate system)
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, str(test_data['business_name']))
                    
                    # Add debug marker
                    can.setFillColorRGB(1, 0, 0)  # Red
                    can.drawString(pos['x'] - 5, pdf_y + 5, "BN")
                    can.setFillColorRGB(0, 0, 0)  # Back to black
                
                # Address
                if 'address' in positions and 'address' in test_data:
                    pos = positions['address']
                    can.setFont(pos.get('font', 'Helvetica'), pos.get('size', 9))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, str(test_data['address']))
                    
                    # Add debug marker
                    can.setFillColorRGB(1, 0, 0)  # Red
                    can.drawString(pos['x'] - 5, pdf_y + 5, "AD")
                    can.setFillColorRGB(0, 0, 0)  # Back to black
                
                # City, State, ZIP
                if 'city_state_zip' in positions and 'city_state_zip' in test_data:
                    pos = positions['city_state_zip']
                    can.setFont(pos.get('font', 'Helvetica'), pos.get('size', 9))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, str(test_data['city_state_zip']))
                    
                    # Add debug marker
                    can.setFillColorRGB(1, 0, 0)  # Red
                    can.drawString(pos['x'] - 5, pdf_y + 5, "CS")
                    can.setFillColorRGB(0, 0, 0)  # Back to black
                
                # Tax Year
                if 'tax_year' in positions and 'tax_year' in test_data:
                    pos = positions['tax_year']
                    can.setFont(pos.get('font', 'Helvetica-Bold'), pos.get('size', 11))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, str(test_data['tax_year']))
                    
                    # Add debug marker
                    can.setFillColorRGB(1, 0, 0)  # Red
                    can.drawString(pos['x'] - 5, pdf_y + 5, "TY")
                    can.setFillColorRGB(0, 0, 0)  # Back to black
                
                # EIN Digits (individual digit positioning)
                if 'ein_digits' in positions and 'ein_digits' in test_data:
                    pos = positions['ein_digits']
                    ein = str(test_data['ein_digits'])
                    if 'x_positions' in pos and len(ein) >= len(pos['x_positions']):
                        can.setFont(pos.get('font', 'Helvetica'), pos.get('size', 10))
                        pdf_y = pos['y']
                        for i, x_pos in enumerate(pos['x_positions']):
                            if i < len(ein):
                                can.drawString(x_pos, pdf_y, ein[i])
                        
                        # Add debug marker for EIN area
                        can.setFillColorRGB(1, 0, 0)  # Red
                        can.drawString(pos['x_positions'][0] - 10, pdf_y + 5, "EIN")
                        can.setFillColorRGB(0, 0, 0)  # Back to black
                
                # === CHECKBOXES SECTION ===
                
                # Set checkbox color to RED for visibility
                can.setFillColorRGB(1, 0, 0)  # Red X marks
                
                # Address Change checkbox
                if 'checkbox_address_change' in positions and test_data.get('checkbox_address_change'):
                    pos = positions['checkbox_address_change']
                    can.setFont(pos.get('font', 'Helvetica-Bold'), pos.get('size', 10))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, "X")
                
                # VIN Correction checkbox
                if 'checkbox_vin_correction' in positions and test_data.get('checkbox_vin_correction'):
                    pos = positions['checkbox_vin_correction']
                    can.setFont(pos.get('font', 'Helvetica-Bold'), pos.get('size', 10))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, "X")
                
                # Amended Return checkbox
                if 'checkbox_amended_return' in positions and test_data.get('checkbox_amended_return'):
                    pos = positions['checkbox_amended_return']
                    can.setFont(pos.get('font', 'Helvetica-Bold'), pos.get('size', 10))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, "X")
                
                # Final Return checkbox
                if 'checkbox_final_return' in positions and test_data.get('checkbox_final_return'):
                    pos = positions['checkbox_final_return']
                    can.setFont(pos.get('font', 'Helvetica-Bold'), pos.get('size', 10))
                    pdf_y = pos['y']
                    can.drawString(pos['x'], pdf_y, "X")
                
                # Reset color to black
                can.setFillColorRGB(0, 0, 0)
                
                # === TEST IDENTIFICATION OVERLAY ===
                # Add a semi-transparent watermark to identify this as a test
                can.setFillColorRGB(1, 0, 0, alpha=0.3)  # Red with transparency
                can.setFont('Helvetica-Bold', 48)
                can.saveState()
                can.translate(306, 400)  # Center of page
                can.rotate(45)  # Diagonal
                can.drawCentredString(0, 0, "TEST PDF")
                can.restoreState()
                
                # Add test generation info in corner
                can.setFillColorRGB(0, 0, 0)  # Black text
                can.setFont('Helvetica', 8)
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                can.drawString(400, 750, f"Generated: {timestamp}")
                can.drawString(400, 740, "Position Tuner Test")
                
                can.save()
                packet.seek(0)
                overlay_page = PdfReader(packet).pages[0]
                overlays.append(overlay_page)
            else:
                overlays.append(None)

        # Merge overlays with template pages
        for idx, page in enumerate(template.pages):
            if overlays[idx]:
                page.merge_page(overlays[idx])
            writer.add_page(page)

        # Create the final PDF
        buffer = io.BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        audit_logger.info("generate_test_pdf: Test PDF with template generated successfully")
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="test_form2290_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        return response
        
    except Exception as e:
        audit_logger.error(f"generate_test_pdf: {str(e)}")
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
        # Sample test data
        test_data = {
            "business_name": "TEST COMPANY LLC",
            "address": "123 Test Street",
            "city": "Test City",
            "state": "TX",
            "zip": "12345",
            "ein": "123456789",
            "tax_year": "2025",
            "address_change": True,
            "vin_correction": False,
            "amended_return": False,
            "final_return": False,
            "vehicles": [
                {
                    "vin": "1HGBH41JXMN109186",
                    "category": "A",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                }
            ]
        }
        
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
        print(f"Processing {len(template.pages)} pages...")
        for page_num in range(1, len(template.pages) + 1):
            print(f"Processing page {page_num}")
            
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
                    
                elif field_name == "ein_digits" and x_positions:
                    ein = test_data["ein"]
                    for i, digit in enumerate(ein):
                        if i < len(x_positions):
                            final_x = x_positions[i] + pdf_x_offset
                            final_y = pos_y + pdf_y_offset
                            can.drawString(final_x, final_y, digit)
                
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
                    
                    if should_check:
                        final_x = pos_x + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, "X")
                
                else:
                    # Generic field rendering with placeholder text
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    placeholder_text = f"[{field_name.replace('_', ' ').title()}]"
                    can.drawString(final_x, final_y, placeholder_text)
            
            can.save()
            packet.seek(0)
            
            # Create overlay page and merge with template page
            overlay_page = PdfReader(packet).pages[0]
            template_page = template.pages[page_num - 1]  # 0-indexed
            template_page.merge_page(overlay_page)
            writer.add_page(template_page)
        
        # Save test PDF
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        test_pdf_path = os.path.join(out_dir, f"offset_test_{timestamp}.pdf")
        
        with open(test_pdf_path, "wb") as f:
            writer.write(f)
        
        return send_file(test_pdf_path, as_attachment=True, download_name=f"offset_test_{timestamp}.pdf")
        
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
