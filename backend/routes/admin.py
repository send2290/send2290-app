"""Admin routes"""
import json
from flask import Blueprint, request, jsonify, make_response, Response
from sqlalchemy import text
from models import SessionLocal, Submission, FilingsDocument
from utils.auth_decorators import verify_admin_token
from services.audit_service import log_admin_action
from services.s3_service import get_s3_client, delete_from_s3
from config import Config

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/submissions', methods=['GET'])
@verify_admin_token
def admin_view_submissions():
    """
    Admin endpoint to view all submissions with user information.
    IRS compliance: Only authorized personnel can access taxpayer data.
    """
    try:
        db = SessionLocal()
        try:
            submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
            
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
                    "user_uid": submission.user_uid,
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
            
            log_admin_action("VIEW_ALL_SUBMISSIONS", f"Retrieved {len(submissions_list)} submissions")
            return jsonify({
                "count": len(submissions_list),
                "submissions": submissions_list
            })
            
        finally:
            db.close()
            
    except Exception as e:
        log_admin_action("VIEW_ALL_SUBMISSIONS_ERROR", f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/submissions/<int:submission_id>', methods=['DELETE'])
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
            if doc.s3_key:
                success, message = delete_from_s3(doc.s3_key)
                if not success:
                    log_admin_action("DELETE_S3_ERROR", f"Failed to delete document S3 file {doc.s3_key}: {message}")
            db.delete(doc)
        
        # Delete submission
        submission = db.query(Submission).get(submission_id)
        if not submission:
            return jsonify({"error": "Submission not found"}), 404
        
        # Delete S3 files
        if submission.xml_s3_key:
            success, message = delete_from_s3(submission.xml_s3_key)
            if not success:
                log_admin_action("DELETE_S3_ERROR", f"Failed to delete XML file {submission.xml_s3_key}: {message}")
        
        if submission.pdf_s3_key:
            success, message = delete_from_s3(submission.pdf_s3_key)
            if not success:
                log_admin_action("DELETE_S3_ERROR", f"Failed to delete PDF file {submission.pdf_s3_key}: {message}")
        
        db.delete(submission)
        db.commit()
        log_admin_action("DELETE_SUCCESS", f"Submission {submission_id} deleted from database")
        return jsonify({"message": "Submission deleted successfully"}), 200
    except Exception as e:
        db.rollback()
        log_admin_action("DELETE_ERROR", f"Failed to delete submission {submission_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@admin_bp.route('/bulk-delete', methods=['POST'])
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
            submission = db.query(Submission).get(submission_id)
            if submission:
                # Delete S3 files
                if submission.xml_s3_key:
                    delete_from_s3(submission.xml_s3_key)
                if submission.pdf_s3_key:
                    delete_from_s3(submission.pdf_s3_key)
                
                # Delete related documents
                docs = db.query(FilingsDocument).filter(FilingsDocument.filing_id == submission_id).all()
                for doc in docs:
                    if doc.s3_key:
                        delete_from_s3(doc.s3_key)
                    db.delete(doc)
                
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

@admin_bp.route('/submissions/<int:submission_id>/download/<file_type>', methods=['GET'])
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
        
        # Download from S3
        try:
            s3 = get_s3_client()
            response = s3.get_object(Bucket=Config.get_bucket_name(), Key=s3_key)
            file_content = response['Body'].read()
            
            # Create response with proper headers
            filename = s3_key.split('/')[-1]
            response = make_response(file_content)
            response.headers['Content-Type'] = content_type
            response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
            
            return response
            
        except Exception as e:
            return jsonify({"error": f"Failed to download file: {str(e)}"}), 500
    
    finally:
        db.close()

@admin_bp.route('/audit-logs', methods=['GET'])
@verify_admin_token
def download_audit_logs():
    """Download audit logs for compliance reporting"""
    try:
        with open(Config.AUDIT_LOG_FILE, 'r') as f:
            logs = f.read()
        
        response = make_response(logs)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = 'attachment; filename=audit.log'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500
