import os
from dotenv import load_dotenv
# ── Load env and set DATABASE_URL ──────────────────────────────────
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./local.db')

import io
import datetime
import boto3
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from xml_builder import build_2290_xml

# ── SQLAlchemy setup ────────────────────────────────────────────────
from sqlalchemy import create_engine, Column, String, Integer, DateTime
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

# Create tables if not exist
Base.metadata.create_all(bind=engine)

# ── Initialize Flask ─────────────────────────────────────────────────
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

# ── Firebase Admin SDK ───────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from functools import wraps

service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
if not os.path.exists(service_account_path):
    raise FileNotFoundError(
        f"\nERROR: 'firebase-service-account.json' not found at: {service_account_path}\n"
        "Please download it from Firebase Console > Service Accounts and place it here."
    )
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)

# ── Boto3 S3 Client ─────────────────────────────────────────────────
s3 = boto3.client(
    's3',
    aws_access_key_id     = os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name           = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)
BUCKET = os.getenv('FILES_BUCKET')

# ── Firebase Token Verifier ───────────────────────────────────────────
def verify_firebase_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
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

# ── Routes ────────────────────────────────────────────────────────────
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
            xml_s3_key=xml_key
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        app.config["last_submission_id"] = submission.id
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

@app.route("/download-pdf", methods=["GET"])
@verify_firebase_token
def download_pdf():
    data = app.config.get("last_form_data") or {}
    template_path = os.path.join(os.path.dirname(__file__), "f2290_template.pdf")
    template = PdfReader(open(template_path, "rb"), strict=False)
    writer = PdfWriter()
    overlays = []

    for pg_idx in range(len(template.pages)):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        if pg_idx == 0:
            can.setFont("Helvetica", 10)
            can.drawString(105, 715, data.get("business_name", ""))
            can.drawString(365, 715, data.get("ein", ""))
        # ...rest of overlay drawing...
        can.save()
        packet.seek(0)
        overlays.append(PdfReader(packet).pages[0])

    for idx, page in enumerate(template.pages):
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

    submission_id = app.config.get("last_submission_id")
    if submission_id:
        db = SessionLocal()
        try:
            sub = db.query(Submission).get(submission_id)
            if sub:
                sub.pdf_s3_key = pdf_key
                db.commit()
        finally:
            db.close()

    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
