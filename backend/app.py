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

# Simple environment detection
IS_PRODUCTION = os.getenv('RENDER') is not None or os.getenv('FLASK_ENV') == 'production'

# Initialize the enhanced audit logger
if IS_PRODUCTION:
    enhanced_audit = IRS2290AuditLogger('production')
    audit_log_file = 'Audit/productionaudit.log'
    print("🔥 PRODUCTION MODE: Using Audit/productionaudit.log")
else:
    enhanced_audit = IRS2290AuditLogger('local')
    audit_log_file = 'Audit/localaudit.log'
    print("🛠️  LOCAL MODE: Using Audit/localaudit.log")

# Keep your existing basic audit logger but point it to the right file
audit_logger = logging.getLogger('basic_audit')
if not audit_logger.handlers:
    audit_handler = logging.FileHandler(audit_log_file)
    audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

def log_admin_action(action, details):
    """Enhanced admin action logging - single entry"""
    user_email = getattr(request, 'user', {}).get('email', 'UNKNOWN_USER')
    
    # Use only enhanced logger to avoid duplicates
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

# API usage logging middleware
@app.before_request
def log_api_requests():
    if request.method == "OPTIONS":
        return
    request.start_time = datetime.datetime.utcnow()

@app.after_request
def log_api_responses(response):
    if request.method == "OPTIONS":
        return response
    
    try:
        # Calculate response time
        response_time_ms = None
        if hasattr(request, 'start_time'):
            response_time = datetime.datetime.utcnow() - request.start_time
            response_time_ms = int(response_time.total_seconds() * 1000)
        
        # Get user email if available
        user_email = 'Anonymous'
        if hasattr(request, 'user') and request.user:
            user_email = request.user.get('email', 'Unknown')
        
        # Log API usage
        audit_logger.log_api_usage(
            user_email=user_email,
            endpoint=request.endpoint or request.path,
            method=request.method,
            response_status=response.status_code,
            response_time_ms=response_time_ms
        )
    except Exception as e:
        # Don't let logging errors break the response
        app.logger.error(f"API logging error: {e}")
    
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

# Initialize audit logger
# Determine environment based on multiple indicators
environment = 'local'  # default
if os.getenv("FLASK_ENV") == "production":
    environment = 'production'
elif os.getenv("FLASK_ENV") != "development":
    # If not explicitly development, check for AWS indicators
    if os.getenv('DATABASE_URL') and not os.getenv('DATABASE_URL').startswith('sqlite'):
        environment = 'production'
    elif os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('FILES_BUCKET'):
        environment = 'production'

print(f"🔍 Audit Logger Environment: {environment}")
audit_logger = IRS2290AuditLogger(environment)

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
            audit_logger.log_security_event("MISSING_AUTH_HEADER", details="Authorization header missing or malformed")
            return jsonify({"error": "Authorization header missing or malformed"}), 401
        token = auth_header.split('Bearer ')[1]
        try:
            decoded = firebase_auth.verify_id_token(token)
            request.user = decoded
            # Log successful authentication (token verification)
            user_email = decoded.get('email', 'Unknown')
            audit_logger.log_login_attempt(user_email, success=True)
        except Exception as e:
            audit_logger.log_login_attempt("Unknown", success=False, failure_reason=str(e))
            audit_logger.log_security_event("INVALID_TOKEN", details=f"Token verification failed: {str(e)}")
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
            audit_logger.log_security_event("ADMIN_ACCESS_NO_TOKEN", details="No valid Bearer token provided")
            log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", "No valid Bearer token provided")
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = firebase_auth.verify_id_token(token)
            
            # Check if user is admin - GET FROM ENVIRONMENT VARIABLE
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@send2290.com')  # Use environment variable
            admin_emails = [admin_email, 'admin@send2290.com']  # Fallback admin
            
            user_email = decoded_token.get('email')
            if user_email not in admin_emails:
                audit_logger.log_security_event("UNAUTHORIZED_ADMIN_ACCESS", user_email, f"Non-admin user attempted admin access")
                log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", f"Non-admin user {user_email} attempted admin access")
                return jsonify({'error': 'Admin access required'}), 403
            
            # Log successful admin authentication
            audit_logger.log_login_attempt(user_email, success=True)
            audit_logger.log_security_event("ADMIN_ACCESS_GRANTED", user_email, f"Admin access granted to {user_email}")
            request.user = decoded_token
            return f(*args, **kwargs)
        except Exception as e:
            audit_logger.log_security_event("ADMIN_INVALID_TOKEN", details=f"Invalid admin token: {str(e)}")
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

# Add user logging to build-xml endpoint
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

            # Create submission record first to get ID for new folder structure
            submission = Submission(
                user_uid=request.user['uid'],
                month=month,
                form_data=json.dumps(month_data)
            )
            db.add(submission)
            db.commit()
            db.refresh(submission)

            # Use submission ID for S3 folder structure
            xml_key = f"submission_{submission.id}/form2290.xml"
            
            # Save XML file with month identifier
            xml_path = os.path.join(os.path.dirname(__file__), f"form2290_{month}.xml")
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_data)

            try:
                with open(xml_path, 'rb') as xml_file:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=xml_key,
                        Body=xml_file,
                        ServerSideEncryption='aws:kms'
                    )
                
                # Update submission with S3 key after successful upload
                submission.xml_s3_key = xml_key
                db.commit()
                
            except Exception as e:
                app.logger.error("S3 XML upload failed for month %s: %s", month, e, exc_info=True)

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
        
        # Log form submissions for each month
        user_email = request.user.get('email', 'Unknown')
        total_vehicles = len(data.get('vehicles', []))
        
        for submission_data in created_submissions:
            try:
                audit_logger.log_form_submission(
                    user_email=user_email,
                    ein=data.get('ein'),
                    tax_year=data.get('tax_year', '2025'),
                    month=submission_data['month'],
                    vehicle_count=submission_data['vehicle_count'],
                    submission_id=submission_data['id']
                )
            except Exception as e:
                app.logger.error(f"Form submission audit logging failed: {e}")
        
        # Log overall submission activity
        try:
            audit_logger.log_data_access(
                user_email=user_email,
                action='CREATE_SUBMISSION',
                data_type='FORM_2290',
                record_count=len(created_submissions)
            )
        except Exception as e:
            app.logger.error(f"Data access audit logging failed: {e}")
    
    finally:
        db.close()

@app.route("/download-xml", methods=["GET"])
@verify_firebase_token
def download_xml():
    user_email = request.user.get('email', 'Unknown')
    xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
    
    if not os.path.exists(xml_path):
        audit_logger.log_error_event(
            user_email=user_email,
            error_type='FILE_NOT_FOUND',
            error_message='XML file not generated yet',
            endpoint='/download-xml'
        )
        return jsonify({"error": "XML not generated yet"}), 404
    
    # Log document access
    audit_logger.log_document_access(
        user_email=user_email,
        action='DOWNLOAD',
        document_type='XML'
    )
    
    return send_file(xml_path, mimetype="application/xml", as_attachment=True)

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
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

            # Create submission record first to get ID for new folder structure
            submission = Submission(
                user_uid=user_uid,
                month=month,
                form_data=json.dumps(month_data)
            )
            db.add(submission)
            db.commit()
            db.refresh(submission)
            filing_id = submission.id

            # Use submission ID for S3 folder structure
            xml_key = f"submission_{filing_id}/form2290.xml"
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
                
                # Update submission with S3 key after successful upload
                submission.xml_s3_key = xml_key
                db.commit()
                
            except Exception as e:
                app.logger.error("S3 XML upload failed for month %s: %s", month, e, exc_info=True)

            # Add XML document record
            db.add(FilingsDocument(
                filing_id=filing_id,
                user_uid=user_uid,
                document_type='xml',
                s3_key=xml_key,
                uploaded_at=datetime.datetime.utcnow()
            ))
            db.commit()

            # Generate PDF for this month
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
                    
                    # Month-specific information
                    can.setFont("Helvetica-Bold", 12)
                    can.drawCentredString(306, 336, f"Month: {month}")
                    
                    # Total Tax Amount for this month
                    can.setFont("Helvetica-Bold", 14)
                    can.drawCentredString(306, 316, f"Total Tax: ${total_tax:,.2f}")
                    
                    # Vehicle Count for this month
                    can.setFont("Helvetica", 12)
                    can.drawCentredString(306, 296, f"Vehicles: {len(month_vehicles)}")
                    
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

            # Save PDF with month identifier
            out_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"form2290_{month}.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)

            # Upload PDF to S3 using submission ID structure
            pdf_key = f"submission_{filing_id}/form2290.pdf"
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
    user_email = request.user.get('email', 'Unknown')
    
    try:
        db = SessionLocal()
        try:
            # Simple query that was working before
            submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
            
            print(f"🔍 ADMIN DEBUG: Found {len(submissions)} total submissions in database")
            
            # Log admin data access
            audit_logger.log_data_access(
                user_email=user_email,
                action='VIEW_ALL_SUBMISSIONS',
                data_type='SUBMISSIONS',
                record_count=len(submissions)
            )
            
            audit_logger.log_admin_action(
                user_email=user_email,
                action='VIEW_ALL_SUBMISSIONS',
                details=f'Retrieved {len(submissions)} submissions'
            )
            
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
    user_email = request.user.get('email', 'Unknown')
    
    # Log the deletion attempt
    audit_logger.log_admin_action(
        user_email=user_email,
        action='DELETE_SUBMISSION_ATTEMPT',
        details=f'Attempting to delete submission ID: {submission_id}'
    )
    log_admin_action("DELETE_SUBMISSION", f"Attempting to delete submission ID: {submission_id}")
    
    db = SessionLocal()
    try:
        # Get submission details for logging before deletion
        submission = db.query(Submission).get(submission_id)
        if not submission:
            audit_logger.log_error_event(
                user_email=user_email,
                error_type='SUBMISSION_NOT_FOUND',
                error_message=f'Submission {submission_id} not found for deletion',
                endpoint='/admin/submissions/delete'
            )
            log_admin_action("DELETE_ERROR", f"Submission {submission_id} not found for deletion")
            return jsonify({"error": "Submission not found"}), 404
        
        # Extract EIN for logging
        form_data = {}
        if submission.form_data:
            try:
                form_data = json.loads(submission.form_data)
            except:
                pass
        
        ein = form_data.get('ein', 'Unknown')
        
        # Delete related documents first
        docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
        for doc in docs:
            try:
                s3.delete_object(Bucket=BUCKET, Key=doc.s3_key)
                audit_logger.log_document_access(
                    user_email=user_email,
                    action='DELETE',
                    document_type=doc.document_type.upper(),
                    document_id=doc.id,
                    ein=ein
                )
                log_admin_action("S3_DELETE", f"Deleted S3 object: {doc.s3_key}")
            except Exception as e:
                audit_logger.log_error_event(
                    user_email=user_email,
                    error_type='S3_DELETE_FAILED',
                    error_message=f'Failed to delete S3 object {doc.s3_key}: {str(e)}',
                    endpoint='/admin/submissions/delete'
                )
                app.logger.warning(f"Failed to delete S3 object {doc.s3_key}: {e}")
            db.delete(doc)
        
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
        
        # Use fallback function to get correct S3 key
        s3_key = get_s3_key_with_fallback(submission, file_type)
        
        if not s3_key:
            return jsonify({"error": f"{file_type.upper()} file not found"}), 404
        
        # Set content type based on file type
        content_type = "application/pdf" if file_type.lower() == "pdf" else "application/xml"
        
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
    user_email = request.user.get('email', 'Unknown')
    
    db = SessionLocal()
    try:
        submissions = db.query(Submission).filter(
            Submission.user_uid == user_uid
        ).order_by(Submission.created_at.desc()).all()
        
        # Log user data access
        audit_logger.log_data_access(
            user_email=user_email,
            action='VIEW_USER_SUBMISSIONS',
            data_type='USER_SUBMISSIONS',
            record_count=len(submissions)
        )
        
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
    user_email = request.user.get('email', 'Unknown')
    
    if file_type not in ['pdf', 'xml']:
        audit_logger.log_error_event(
            user_email=user_email,
            error_type='INVALID_FILE_TYPE',
            error_message=f'Invalid file type requested: {file_type}',
            endpoint='/user/submissions/download'
        )
        return jsonify({"error": "Invalid file type. Must be 'pdf' or 'xml'"}), 400
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(
            Submission.id == submission_id,
            Submission.user_uid == user_uid
        ).first()
        
        if not submission:
            audit_logger.log_security_event(
                'UNAUTHORIZED_FILE_ACCESS',
                user_email,
                f'User attempted to access submission {submission_id} not owned by them'
            )
            return jsonify({"error": "Submission not found"}), 404
        
        # Get form data to extract EIN for logging
        form_data = {}
        if submission.form_data:
            try:
                form_data = json.loads(submission.form_data)
            except:
                pass
        
        # Get the appropriate S3 key using fallback function
        xml_s3_key = get_s3_key_with_fallback(submission, 'xml')
        pdf_s3_key = get_s3_key_with_fallback(submission, 'pdf')
        
        # Use the found keys for download
        s3_key = pdf_s3_key if file_type == 'pdf' else xml_s3_key
        
        if not s3_key:
            audit_logger.log_error_event(
                user_email=user_email,
                error_type='FILE_NOT_FOUND',
                error_message=f'{file_type.upper()} file not found for submission {submission_id}',
                endpoint='/user/submissions/download'
            )
            return jsonify({"error": f"{file_type.upper()} file not found for this submission"}), 404
        
        # Log document access
        audit_logger.log_document_access(
            user_email=user_email,
            action='DOWNLOAD',
            document_type=file_type.upper(),
            document_id=submission_id,
            ein=form_data.get('ein')
        )
        
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

@app.route("/admin/audit-logs/<log_type>", methods=["GET"])
@verify_admin_token
def get_audit_logs(log_type):
    """Get audit logs for specific environment"""
    try:
        if log_type == 'local':
            filename = os.path.join('Audit', 'localaudit.log')
        elif log_type == 'production':
            filename = os.path.join('Audit', 'productionaudit.log')
        else:
            return jsonify({"error": "Invalid log type. Use 'local' or 'production'"}), 400
        
        if not os.path.exists(filename):
            return jsonify({"error": f"Log file {filename} not found"}), 404
            
        with open(filename, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:]  # Last 100 entries
        
        return jsonify({
            "environment": log_type,
            "logs": recent_lines,
            "total_lines": len(lines),
            "showing_last": len(recent_lines),
            "filename": filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/audit-logs/<log_type>/download", methods=["GET"])
@verify_admin_token
def download_audit_logs(log_type):
    """Download complete audit log file"""
    try:
        if log_type == 'local':
            filename = 'localaudit.log'
        elif log_type == 'production':
            filename = 'productionaudit.log'
        else:
            return jsonify({"error": "Invalid log type"}), 400
        
        if not os.path.exists(filename):
            return jsonify({"error": f"Log file {filename} not found"}), 404
            
        return send_file(filename, as_attachment=True, download_name=f'{log_type}_audit_{datetime.now().strftime("%Y%m%d")}.log')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_s3_key_with_fallback(submission, file_type):
    """
    Get S3 key for a file, with fallback to check both old and new structures.
    This ensures compatibility during the migration period.
    """
    if file_type == 'pdf':
        primary_key = submission.pdf_s3_key
    else:  # xml
        primary_key = submission.xml_s3_key
    
    # If we have a key in database, check if it exists in S3
    if primary_key:
        try:
            s3.head_object(Bucket=BUCKET, Key=primary_key)
            return primary_key
        except:
            # File doesn't exist at recorded location
            pass
    
    # Try new structure
    new_key = f"submission_{submission.id}/form2290.{file_type}"
    try:
        s3.head_object(Bucket=BUCKET, Key=new_key)
        return new_key
    except:
        pass
    
    # Try old structure if we can reconstruct it
    if submission.user_uid and submission.month:
        old_key = f"{submission.user_uid}/{submission.month}/form2290.{file_type}"
        try:
            s3.head_object(Bucket=BUCKET, Key=old_key)
            return old_key
        except:
            pass
    
    # Return the primary key even if file doesn't exist (for error handling)
    return primary_key

if __name__ == "__main__":
    print("🔥 Starting Flask development server...")
    print(f"🔧 Flask ENV: {os.getenv('FLASK_ENV', 'development')}")
    print(f"🗄️  Database: {DATABASE_URL[:50]}...")
    
    # Test database connection
    try:
        with engine.connect() as conn:
            print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise
    
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)