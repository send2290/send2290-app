"""User routes"""
import json
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import text
from models import SessionLocal, Submission, FilingsDocument
from utils.auth_decorators import verify_firebase_token
from services.s3_service import get_s3_client, generate_presigned_url
from config import Config

user_bp = Blueprint('user', __name__)

@user_bp.route('/submissions', methods=['GET'])
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
                except:
                    form_data = {}
            
            # Calculate totals from vehicles data
            vehicles = form_data.get('vehicles', [])
            total_vehicles = len(vehicles)
            
            # Get tax from frontend's calculation
            total_tax = 0
            frontend_part_i = form_data.get('partI', {})
            if frontend_part_i and 'line2_tax' in frontend_part_i:
                try:
                    total_tax = float(frontend_part_i['line2_tax'])
                except:
                    total_tax = 0
            
            submissions_list.append({
                "id": str(submission.id),
                "business_name": form_data.get("business_name", "Unknown Business"),
                "ein": form_data.get("ein", "Unknown EIN"),
                "created_at": submission.created_at.isoformat() if submission.created_at else "",
                "month": submission.month,
                "total_vehicles": total_vehicles,
                "total_tax": round(total_tax, 2),
                "status": "Submitted",
                "xml_s3_key": submission.xml_s3_key,
                "pdf_s3_key": submission.pdf_s3_key
            })
        
        return jsonify({
            "count": len(submissions_list),
            "submissions": submissions_list
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch submissions"}), 500
    finally:
        db.close()

@user_bp.route('/documents', methods=['GET'])
@verify_firebase_token
def user_documents():
    """Get all documents for the current user"""
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
            success, url = generate_presigned_url(s3_key, expiration=900)
            
            if submission_id not in submissions:
                submissions[submission_id] = {
                    "id": submission_id,
                    "month": month,
                    "created_at": created_at.isoformat() if created_at else "",
                    "documents": []
                }
            
            if success:
                submissions[submission_id]["documents"].append({
                    "type": doc_type,
                    "url": url
                })

        return jsonify({
            "count": len(submissions),
            "submissions": list(submissions.values())
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch documents"}), 500
    finally:
        db.close()

@user_bp.route('/submissions/<submission_id>/download/<file_type>', methods=['GET'])
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
            return jsonify({"error": f"{file_type.upper()} file not found"}), 404
        
        # Fetch the file from S3 and return it as a download
        try:
            s3 = get_s3_client()
            response = s3.get_object(Bucket=Config.get_bucket_name(), Key=s3_key)
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
            
        except Exception as e:
            return jsonify({"error": "Download failed"}), 500
    
    except Exception as e:
        return jsonify({"error": "Failed to download file"}), 500
    finally:
        db.close()

@user_bp.route('/submissions/<month>/download-pdf', methods=['GET'])
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
        success, url = generate_presigned_url(submission.pdf_s3_key, expiration=300)
        if success:
            return jsonify({"download_url": url}), 200
        else:
            return jsonify({"error": "Failed to generate download link"}), 500
    
    finally:
        db.close()
