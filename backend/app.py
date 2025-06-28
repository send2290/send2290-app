import os
import datetime
import json
import io
import logging
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

# Set up audit logging for IRS compliance
audit_logger = logging.getLogger('audit')
audit_handler = logging.FileHandler('audit.log')
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

def log_admin_action(action, details):
    """Log admin actions for IRS audit trail compliance"""
    user_email = getattr(request, 'user', {}).get('email', 'UNKNOWN_USER')
    audit_logger.info(f"ADMIN_ACTION: {action} | USER: {user_email} | DETAILS: {details}")

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:3000",
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
    # data = store_user_email_in_submission(data, request.user)  # Store email in form data

    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    try:
        xml_data = build_2290_xml(data)
    except Exception as e:
        app.logger.error("Error building XML: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

    if isinstance(xml_data, bytes):
        xml_data = xml_data.decode('utf-8', errors='ignore')

    xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_data)

    xml_key = f"{request.user['uid']}/{data.get('used_on_july','')}/form2290.xml"
    try:
        with open(xml_path, 'rb') as xml_file:
            s3.put_object(
                Bucket=BUCKET,
                Key=xml_key,
                Body=xml_file,
                ServerSideEncryption='aws:kms'
            )
    except Exception as e:
        app.logger.error("S3 XML upload failed: %s", e, exc_info=True)

    db = SessionLocal()
    try:
        submission = Submission(
            user_uid=request.user['uid'],
            month=data.get('used_on_july',''),
            xml_s3_key=xml_key,
            form_data=json.dumps(data)
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        app.config["last_submission_id"] = submission.id

        db.add(FilingsDocument(
            filing_id=submission.id,
            user_uid=request.user['uid'],
            document_type='xml',
            s3_key=xml_key,
            uploaded_at=datetime.datetime.utcnow()
        ))
        db.commit()
    finally:
        db.close()

    app.config["last_form_data"] = data
    return jsonify({"message": "✅ XML generated", "xml": xml_data}), 200

@app.route("/download-xml", methods=["GET"])
@verify_firebase_token
def download_xml():
    xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
    if not os.path.exists(xml_path):
        return jsonify({"error": "XML not generated yet"}), 404
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

    writer = PdfWriter()
    overlays = []

    for pg_idx in range(len(template.pages)):
        if pg_idx == 0:
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont("Helvetica-Bold", 16)
            can.drawCentredString(306, 396, data.get("business_name", ""))
            can.setFont("Helvetica", 14)
            can.drawCentredString(306, 376, data.get("address", ""))
            can.drawCentredString(306, 356, f"EIN: {data.get('ein', '')}")
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
    # data = store_user_email_in_submission(data, request.user)  # Store email in form data

    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    user_uid = request.user['uid']
    month = data.get('used_on_july', '')
    
    db = SessionLocal()
    try:
        # Find existing submission for this user and month
        existing_submission = db.query(Submission).filter(
            Submission.user_uid == user_uid,
            Submission.month == month
        ).order_by(Submission.created_at.desc()).first()
        
        if existing_submission:
            # Update existing submission with PDF
            filing_id = existing_submission.id
            print(f"📝 Updating existing submission {filing_id} with PDF")
            
            # Update the form data in case user made changes
            existing_submission.form_data = json.dumps(data)
            db.commit()
        else:
            # Create new submission (normal flow)
            print(f"✨ Creating new submission for user {user_uid}, month {month}")
            
            # Generate XML first
            try:
                xml_data = build_2290_xml(data)
            except Exception as e:
                app.logger.error("Error building XML: %s", e, exc_info=True)
                return jsonify({"error": str(e)}), 500

            xml_key = f"{user_uid}/{month}/form2290.xml"
            xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
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
                app.logger.error("S3 XML upload failed: %s", e, exc_info=True)

            # Create submission record
            submission = Submission(
                user_uid=user_uid,
                month=month,
                xml_s3_key=xml_key,
                form_data=json.dumps(data)
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

        # Generate PDF
        template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
        template = PdfReader(open(template_path, "rb"), strict=False)
        writer = PdfWriter()
        overlays = []

        for pg_idx in range(len(template.pages)):
            if pg_idx == 0:
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                can.setFont("Helvetica-Bold", 16)
                can.drawCentredString(306, 396, data.get("business_name", ""))
                can.setFont("Helvetica", 14)
                can.drawCentredString(306, 376, data.get("address", ""))
                can.drawCentredString(306, 356, f"EIN: {data.get('ein', '')}")
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
            app.logger.error("S3 PDF upload failed: %s", e, exc_info=True)

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

        print(f"✅ Form 2290 completed for submission {filing_id}")
        return send_file(out_path, as_attachment=True)
    
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
                total_tax = sum(float(v.get('tax_amount', 0)) for v in vehicles)
                
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
    log_admin_action("DELETE_SUBMISSION", f"Deleted submission ID: {submission_id}")
    
    db = SessionLocal()
    try:
        # Delete related documents first
        docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
        for doc in docs:
            # Delete from S3
            try:
                s3.delete_object(Bucket=BUCKET, Key=doc.s3_key)
                log_admin_action("S3_DELETE", f"Deleted S3 object: {doc.s3_key}")
            except Exception as e:
                app.logger.warning(f"Failed to delete S3 object {doc.s3_key}: {e}")
            db.delete(doc)
        
        # Delete submission
        submission = db.query(Submission).get(submission_id)
        if not submission:
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

@app.route("/admin/submissions/<int:submission_id>/files", methods=["GET"])
@verify_admin_token
def admin_view_submission_files(submission_id):
    """
    Secure endpoint to view PDF/XML files for a specific submission.
    Returns download links for the files with proper audit logging.
    """
    log_admin_action("VIEW_SUBMISSION_FILES", f"Viewed files for submission ID: {submission_id}")
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).get(submission_id)
        if not submission:
            return jsonify({"error": "Submission not found"}), 404
        
        files = []
        
        # Add PDF file if exists
        if submission.pdf_s3_key:
            files.append({
                "type": "PDF",
                "filename": submission.pdf_s3_key.split('/')[-1],
                "download_url": f"/admin/submissions/{submission_id}/download/pdf",
                "s3_key": submission.pdf_s3_key
            })
        
        # Add XML file if exists
        if submission.xml_s3_key:
            files.append({
                "type": "XML",
                "filename": submission.xml_s3_key.split('/')[-1],
                "download_url": f"/admin/submissions/{submission_id}/download/xml",
                "s3_key": submission.xml_s3_key
            })
        
        # Add any additional documents
        docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
        for doc in docs:
            files.append({
                "type": doc.document_type.upper(),
                "filename": doc.s3_key.split('/')[-1] if doc.s3_key else "unknown",
                "download_url": f"/admin/documents/{doc.id}/download",
                "s3_key": doc.s3_key
            })
        
        return jsonify({
            "submission_id": submission_id,
            "files": files,
            "total_files": len(files)
        })
    
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

@app.route("/user/documents", methods=["GET"])
@verify_firebase_token
def user_documents():
    """
    Endpoint for users to view their submitted documents.
    Returns a list of documents with metadata and download links.
    """
    user_uid = request.user['uid']
    db = SessionLocal()
    try:
        # Query to fetch user's submissions and associated documents
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

        return jsonify({
            "count": len(submissions),
            "submissions": list(submissions.values())
        })
    finally:
        db.close()

if __name__ == "__main__":
    print("🔥 Starting Flask development server...")
    print(f"🔧 Flask ENV: {os.getenv('FLASK_ENV', 'development')}")
    print(f"🗄️  Database: {DATABASE_URL[:50]}...")
    
    # Test database connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Check AWS RDS security group settings")
        
    print(f"🪣 S3 Bucket: {BUCKET}")
    print(f"👨‍💼 Admin Email: {os.getenv('ADMIN_EMAIL')}")
    
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
