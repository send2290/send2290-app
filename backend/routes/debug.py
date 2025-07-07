"""Debug and testing routes"""
import datetime
from flask import Blueprint, jsonify
from sqlalchemy import text
from models import SessionLocal, Submission, FilingsDocument
from config import Config
from utils.auth_decorators import verify_admin_token
from services.s3_service import get_s3_client, test_s3_connection

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/db-info', methods=['GET'])
def debug_db_info():
    """Get database information"""
    from models import Base, engine
    return jsonify({
        "DATABASE_URL": Config.DATABASE_URL,
        "engine_url": str(engine.url),
        "table_names": list(Base.metadata.tables.keys())
    }), 200

@debug_bp.route('/submissions', methods=['GET'])
def debug_submissions():
    """Get all submissions for debugging"""
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

@debug_bp.route('/filings-documents', methods=['GET'])
def debug_filings_documents():
    """Get all filing documents for debugging"""
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

@debug_bp.route('/s3-test', methods=['GET'])
@verify_admin_token
def debug_s3_test():
    """Test S3 connectivity and list bucket contents"""
    try:
        s3 = get_s3_client()
        bucket = Config.get_bucket_name()
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=10)
        
        objects = []
        if 'Contents' in response:
            for obj in response['Contents']:
                objects.append({
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat()
                })
        
        return jsonify({
            "bucket": bucket,
            "accessible": True,
            "object_count": len(objects),
            "sample_objects": objects[:5]
        })
    except Exception as e:
        return jsonify({
            "bucket": Config.get_bucket_name(),
            "accessible": False,
            "error": str(e)
        }), 500
