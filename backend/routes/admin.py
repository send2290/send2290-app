"""Admin routes"""
import json
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, make_response, Response
from sqlalchemy import text, or_
from models import SessionLocal, Submission, FilingsDocument, PaymentIntent
from utils.auth_decorators import verify_admin_token
from services.audit_service import log_admin_action
from services.s3_service import get_s3_client, delete_from_s3
from config import Config

def format_est_timestamp(dt):
    """Convert UTC datetime to Eastern Time with EST/EDT label"""
    if not dt:
        return ""
    
    # Create Eastern timezone (UTC-5 for EST, UTC-4 for EDT)
    eastern = timezone(timedelta(hours=-5))  # EST (we'll use EST year-round for simplicity)
    
    # Convert to Eastern time
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    
    eastern_time = dt.astimezone(eastern)
    
    # Format as "MMM DD, YYYY, HH:MM AM/PM EST"
    return eastern_time.strftime("%b %d, %Y, %I:%M %p EST")

def get_user_email_from_form_data(form_data_json):
    """Extract user email from form_data JSON"""
    try:
        if form_data_json:
            form_data = json.loads(form_data_json)
            return form_data.get('email', 'Unknown')
    except:
        pass
    return 'Unknown'

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/submissions', methods=['GET'])
@verify_admin_token
def admin_view_submissions():
    """
    Admin endpoint to view all submissions with user information.
    IRS compliance: Only authorized personnel can access taxpayer data.
    """
    try:
        # Get optional filters from query parameters
        user_filter = request.args.get('user_filter', '').strip()
        email_filter = request.args.get('email_filter', '').strip()
        
        db = SessionLocal()
        try:
            # Start with base query
            query = db.query(Submission).order_by(Submission.created_at.desc())
            
            # Apply filters if provided
            if user_filter:
                query = query.filter(Submission.user_uid.ilike(f'%{user_filter}%'))
            
            if email_filter:
                # Search in form_data JSON for email
                query = query.filter(Submission.form_data.ilike(f'%{email_filter}%'))
            
            submissions = query.all()
            
            submissions_list = []
            for submission in submissions:
                # Parse form_data to get business info if available
                form_data = {}
                if submission.form_data:
                    try:
                        form_data = json.loads(submission.form_data)
                    except:
                        form_data = {}
                
                # Get user email from form data
                user_email = get_user_email_from_form_data(submission.form_data)
                
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
                    "user_email": user_email,  # Now includes actual email
                    "business_name": form_data.get("business_name", "Unknown Business"),
                    "ein": form_data.get("ein", "Unknown EIN"),
                    "created_at": format_est_timestamp(submission.created_at),
                    "month": submission.month,
                    "total_vehicles": total_vehicles,
                    "total_tax": round(total_tax, 2),
                    "status": "Submitted",
                    "xml_s3_key": submission.xml_s3_key,
                    "pdf_s3_key": submission.pdf_s3_key
                })
            
            log_admin_action("VIEW_ALL_SUBMISSIONS", f"Retrieved {len(submissions_list)} submissions (filters: user={user_filter}, email={email_filter})")
            return jsonify({
                "count": len(submissions_list),
                "submissions": submissions_list,
                "filters": {
                    "user_filter": user_filter,
                    "email_filter": email_filter
                }
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

@admin_bp.route('/payment-history', methods=['GET'])
@verify_admin_token
def admin_view_payment_history():
    """
    Admin endpoint to view payment intent history
    """
    try:
        # Get optional filters from query parameters
        user_filter = request.args.get('user_filter', '').strip()
        email_filter = request.args.get('email_filter', '').strip()
        
        db = SessionLocal()
        try:
            # Start with base query
            query = db.query(PaymentIntent).order_by(PaymentIntent.created_at.desc())
            
            # Apply user filter if provided
            if user_filter:
                query = query.filter(PaymentIntent.user_uid.ilike(f'%{user_filter}%'))
            
            payment_intents = query.all()
            
            # If email filter is provided, we need to cross-reference with submissions
            if email_filter:
                # Get user UIDs that match the email filter from submissions
                submission_query = db.query(Submission.user_uid).filter(
                    Submission.form_data.ilike(f'%{email_filter}%')
                ).distinct()
                matching_user_uids = [s.user_uid for s in submission_query.all()]
                
                if matching_user_uids:
                    query = query.filter(PaymentIntent.user_uid.in_(matching_user_uids))
                    payment_intents = query.all()
                else:
                    payment_intents = []  # No matching users found
            
            payment_list = []
            for payment in payment_intents:
                # Try to get user email from a submission with the same user_uid
                user_email = "Unknown"
                submission = db.query(Submission).filter(Submission.user_uid == payment.user_uid).first()
                if submission:
                    user_email = get_user_email_from_form_data(submission.form_data)
                
                payment_list.append({
                    "id": str(payment.id),
                    "payment_intent_id": payment.payment_intent_id,
                    "user_uid": payment.user_uid,
                    "user_email": user_email,
                    "amount_dollars": round(payment.amount_cents / 100, 2),
                    "status": payment.status,
                    "used_for_preview": payment.used_for_preview == 'true',
                    "used_for_submission": payment.used_for_submission == 'true',
                    "submission_id": payment.submission_id,
                    "created_at": format_est_timestamp(payment.created_at),
                    "updated_at": format_est_timestamp(payment.updated_at)
                })
            
            log_admin_action("VIEW_PAYMENT_HISTORY", f"Retrieved {len(payment_list)} payment intents (filters: user={user_filter}, email={email_filter})")
            return jsonify({
                "count": len(payment_list),
                "payments": payment_list,
                "filters": {
                    "user_filter": user_filter,
                    "email_filter": email_filter
                }
            })
            
        finally:
            db.close()
            
    except Exception as e:
        log_admin_action("VIEW_PAYMENT_HISTORY_ERROR", f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/user-details/<user_identifier>', methods=['GET'])
@verify_admin_token
def admin_view_user_details(user_identifier):
    """
    Admin endpoint to view detailed information for a specific user
    Can search by user_uid or email
    """
    try:
        db = SessionLocal()
        try:
            # Determine if searching by email or UID
            if '@' in user_identifier:
                # Search by email in form_data
                submissions = db.query(Submission).filter(
                    Submission.form_data.ilike(f'%{user_identifier}%')
                ).order_by(Submission.created_at.desc()).all()
                
                # Get user_uid from first submission
                user_uid = submissions[0].user_uid if submissions else None
            else:
                # Search by user_uid
                user_uid = user_identifier
                submissions = db.query(Submission).filter(
                    Submission.user_uid == user_uid
                ).order_by(Submission.created_at.desc()).all()
            
            if not submissions:
                return jsonify({"error": "User not found"}), 404
            
            # Get payment history for this user
            payments = db.query(PaymentIntent).filter(
                PaymentIntent.user_uid == user_uid
            ).order_by(PaymentIntent.created_at.desc()).all()
            
            # Format user details
            user_email = get_user_email_from_form_data(submissions[0].form_data)
            
            user_details = {
                "user_uid": user_uid,
                "user_email": user_email,
                "total_submissions": len(submissions),
                "total_payments": len(payments),
                "total_amount_paid": sum(p.amount_cents for p in payments if p.status == 'succeeded') / 100,
                "submissions": [],
                "payments": []
            }
            
            # Add submission details
            for submission in submissions:
                form_data = {}
                if submission.form_data:
                    try:
                        form_data = json.loads(submission.form_data)
                    except:
                        form_data = {}
                
                vehicles = form_data.get('vehicles', [])
                total_tax = 0
                frontend_part_i = form_data.get('partI', {})
                if frontend_part_i and 'line2_tax' in frontend_part_i:
                    try:
                        total_tax = float(frontend_part_i['line2_tax'])
                    except:
                        total_tax = 0
                
                user_details["submissions"].append({
                    "id": str(submission.id),
                    "business_name": form_data.get("business_name", "Unknown Business"),
                    "ein": form_data.get("ein", "Unknown EIN"),
                    "created_at": format_est_timestamp(submission.created_at),
                    "month": submission.month,
                    "total_vehicles": len(vehicles),
                    "total_tax": round(total_tax, 2),
                    "xml_s3_key": submission.xml_s3_key,
                    "pdf_s3_key": submission.pdf_s3_key
                })
            
            # Add payment details
            for payment in payments:
                user_details["payments"].append({
                    "id": str(payment.id),
                    "payment_intent_id": payment.payment_intent_id,
                    "amount_dollars": round(payment.amount_cents / 100, 2),
                    "status": payment.status,
                    "used_for_preview": payment.used_for_preview == 'true',
                    "used_for_submission": payment.used_for_submission == 'true',
                    "submission_id": payment.submission_id,
                    "created_at": format_est_timestamp(payment.created_at),
                    "updated_at": format_est_timestamp(payment.updated_at)
                })
            
            log_admin_action("VIEW_USER_DETAILS", f"Retrieved details for user: {user_identifier}")
            return jsonify(user_details)
            
        finally:
            db.close()
            
    except Exception as e:
        log_admin_action("VIEW_USER_DETAILS_ERROR", f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
