import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./local.db')

import io
import datetime
import boto3
import botocore
from flask import Flask, request, jsonify, send_file, make_response, g
from flask_cors import CORS
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from xml_builder import build_2290_xml
import json

from sqlalchemy import create_engine, Column, String, Integer, DateTime, text, JSON, Text
from sqlalchemy.orm import sessionmaker, declarative_base

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

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from functools import wraps

if os.getenv("FLASK_ENV") == "development":
    service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
else:
    service_account_path = "/etc/secrets/firebase-service-account.json"

if not os.path.exists(service_account_path):
    raise FileNotFoundError(
        f"\nERROR: service account JSON not found at: {service_account_path}\n"
        "If running locally, set FLASK_ENV=development and place firebase-service-account.json in the backend folder.\n"
        "In production, ensure it is mounted at /etc/secrets/firebase-service-account.json."
    )

cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)

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

@app.route("/build-pdf", methods=["POST"])
@verify_firebase_token
def build_pdf():
    data = request.get_json() or {}
    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    # 1. Generate XML and save Submission
    try:
        xml_data = build_2290_xml(data)
    except Exception as e:
        app.logger.error("Error building XML: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

    xml_key = f"{request.user['uid']}/{data.get('used_on_july','')}/form2290.xml"
    xml_path = os.path.join(os.path.dirname(__file__), "form2290.xml")
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
        filing_id = submission.id

        db.add(FilingsDocument(
            filing_id=filing_id,
            user_uid=request.user['uid'],
            document_type='xml',
            s3_key=xml_key,
            uploaded_at=datetime.datetime.utcnow()
        ))
        db.commit()
    finally:
        db.close()

    # 2. Generate PDF using the same data (minimal overlay)
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

    pdf_key = f"{request.user['uid']}/{data.get('used_on_july','')}/form2290.pdf"
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

    db = SessionLocal()
    try:
        sub = db.query(Submission).get(filing_id)
        if sub:
            sub.pdf_s3_key = pdf_key
            db.commit()
        db.add(FilingsDocument(
            filing_id=filing_id,
            user_uid=request.user['uid'],
            document_type='pdf',
            s3_key=pdf_key,
            uploaded_at=datetime.datetime.utcnow()
        ))
        db.commit()
    finally:
        db.close()

    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
