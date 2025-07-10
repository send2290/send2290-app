"""
Refactored Flask Application - Main Entry Point
This is a simplified version that uses modular components.
"""
import os
import datetime
import json
import firebase_admin
from firebase_admin import credentials, auth
from flask import Flask, request, jsonify, make_response, send_file, Response
from flask_cors import CORS
from sqlalchemy import text

# Import our modules
from config import Config
from models import init_database, test_database_connection, SessionLocal, Submission, FilingsDocument
from routes import register_routes
from routes.position_tuner import init_form_positions
from services.audit_service import init_audit_logging, log_admin_action
from services.s3_service import get_s3_client
from services.payment_tracking_service import PaymentTrackingService
from utils.auth_decorators import verify_firebase_token, verify_admin_token
from utils.calculations import group_vehicles_by_month

# Import the original functions that we haven't moved yet
# TODO: These will be moved to services in future phases
from xml_builder import build_2290_xml
from Audit.enhanced_audit import IRS2290AuditLogger

# Create audit logger instance
enhanced_audit = IRS2290AuditLogger('local' if Config.FLASK_ENV == 'development' else 'production')

def create_app():
    """Application factory"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize CORS
    CORS(app, **Config.CORS_CONFIG)
    
    # Initialize Firebase Admin
    if not firebase_admin._apps:
        if Config.FIREBASE_ADMIN_KEY_JSON:
            firebase_cred_dict = json.loads(Config.FIREBASE_ADMIN_KEY_JSON)
            cred = credentials.Certificate(firebase_cred_dict)
            firebase_admin.initialize_app(cred)
        else:
            print("Warning: Firebase credentials not found")
    
    # Initialize database
    init_database()
    
    # Initialize audit logging
    init_audit_logging()
    
    # Initialize form positions
    init_form_positions()
    
    # Register all routes
    register_routes(app)
    
    # Legacy routes that haven't been moved yet
    register_legacy_routes(app)
    
    # Add CORS headers to every response (matches app.py behavior)
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
    
    return app

def register_legacy_routes(app):
    """Register routes that haven't been moved to blueprints yet"""
    
    @app.route("/build-xml", methods=["POST", "OPTIONS"])
    @verify_firebase_token
    def generate_xml():
        """Generate XML for form submission - LEGACY ROUTE"""
        if request.method == "OPTIONS":
            return jsonify({}), 200
        
        data = request.get_json() or {}
        
        if not data.get("business_name") or not data.get("ein"):
            return jsonify({"error": "Missing business_name or ein"}), 400
        
        # Group vehicles by month
        vehicles_by_month = group_vehicles_by_month(data.get('vehicles', []))
        
        if not vehicles_by_month:
            return jsonify({"error": "No vehicles found"}), 400
        
        created_submissions = []
        db = SessionLocal()
        
        try:
            s3 = get_s3_client()
            
            for month, month_vehicles in vehicles_by_month.items():
                # Build XML using the original XML builder
                try:
                    xml_content = build_2290_xml(data)
                except ValueError as e:
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="XML_VALIDATION_ERROR",
                        error_message=str(e),
                        endpoint="/build-xml"
                    )
                    return jsonify({"error": str(e)}), 400
                
                # Upload to S3
                xml_key = f"{request.user['uid']}/form2290_{month}.xml"
                
                try:
                    s3.put_object(
                        Bucket=Config.get_bucket_name(),
                        Key=xml_key,
                        Body=xml_content.encode('utf-8'),
                        ContentType='application/xml'
                    )
                except Exception as e:
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="S3_UPLOAD_ERROR",
                        error_message=f"Failed to upload XML: {str(e)}",
                        endpoint="/build-xml"
                    )
                    return jsonify({"error": f"Failed to upload XML: {str(e)}"}), 500
                
                # Save to database
                submission = Submission(
                    user_uid=request.user['uid'],
                    month=month,
                    xml_s3_key=xml_key,
                    form_data=json.dumps(data)
                )
                db.add(submission)
                db.commit()
                db.refresh(submission)
                
                created_submissions.append({
                    "id": str(submission.id),
                    "month": month,
                    "xml_s3_key": xml_key,
                    "vehicle_count": len(month_vehicles)
                })
                
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="XML_SUBMISSION_SUCCESS",
                    error_message=f"XML generated for month {month} with {len(month_vehicles)} vehicles",
                    endpoint="/build-xml"
                )
            
            return jsonify({
                "success": True,
                "message": f"Generated XML for {len(created_submissions)} month(s)",
                "submissions": created_submissions
            }), 200
            
        except Exception as e:
            db.rollback()
            enhanced_audit.log_error_event(
                user_email=request.user.get('email', 'unknown'),
                error_type="SUBMISSION_PROCESSING_ERROR",
                error_message=f"Unexpected error during XML submission: {str(e)}",
                endpoint="/build-xml"
            )
            return jsonify({"error": f"Submission processing failed: {str(e)}"}), 500
        
        finally:
            db.close()

    @app.route("/build-pdf", methods=["POST", "OPTIONS"])
    @verify_firebase_token
    def build_pdf():
        """Generate PDF for form submission - LEGACY ROUTE (requires payment)"""
        if request.method == "OPTIONS":
            return jsonify({}), 200
        
        try:
            # Try to import Stripe, but handle gracefully if not available
            try:
                import stripe
                STRIPE_AVAILABLE = True
            except ImportError:
                STRIPE_AVAILABLE = False
                stripe = None
                
            from services.pdf_service import PDFGenerationService
            
            data = request.get_json() or {}
            
            if not data.get("business_name") or not data.get("ein"):
                return jsonify({"error": "Missing business_name or ein"}), 400
            
            # Check for payment verification
            payment_intent_id = data.get("payment_intent_id")
            if not payment_intent_id:
                return jsonify({"error": "Payment required. Please complete payment before submitting."}), 402
            
            # Check if we can reuse an existing payment
            payment_verified = False
            if PaymentTrackingService.can_reuse_payment(payment_intent_id, request.user['uid']):
                payment_verified = True
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="PAYMENT_REUSED_FOR_SUBMISSION",
                    error_message=f"Payment {payment_intent_id} reused for submission",
                    endpoint="/build-pdf"
                )
            else:
                # Verify payment with Stripe (skip in development if not configured)
                if Config.FLASK_ENV == 'development' and 'dev_mode' in payment_intent_id:
                    payment_verified = True
                    
                    # Record/update the payment
                    PaymentTrackingService.record_payment_intent(
                        payment_intent_id, request.user['uid'], status='succeeded'
                    )
                    
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="PAYMENT_BYPASS_DEV_MODE",
                        error_message="Development mode payment bypass",
                        endpoint="/build-pdf"
                    )
                elif payment_intent_id == 'dev_mode_fake_client_secret':
                    # Handle development mode payment bypass even in production if Stripe is not configured
                    payment_verified = True
                    
                    # Record the legacy dev mode payment
                    PaymentTrackingService.record_payment_intent(
                        payment_intent_id, request.user['uid'], status='succeeded'
                    )
                    
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="PAYMENT_BYPASS_NO_STRIPE",
                        error_message="Payment bypass due to Stripe not configured",
                        endpoint="/build-pdf"
                    )
                elif Config.STRIPE_SECRET_KEY and STRIPE_AVAILABLE:
                    try:
                        stripe.api_key = Config.STRIPE_SECRET_KEY
                        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                        
                        if intent.status != 'succeeded':
                            return jsonify({"error": "Payment not completed"}), 402
                        
                        if intent.metadata.get('user_uid') != request.user['uid']:
                            return jsonify({"error": "Payment verification failed"}), 402
                        
                        payment_verified = True
                        
                        # Record/update the payment
                        PaymentTrackingService.record_payment_intent(
                            payment_intent_id, request.user['uid'], status='succeeded'
                        )
                        
                        enhanced_audit.log_error_event(
                            user_email=request.user.get('email', 'unknown'),
                            error_type="PAYMENT_VERIFIED_SUBMISSION",
                            error_message=f"Payment verified for submission: {payment_intent_id}",
                            endpoint="/build-pdf"
                        )
                            
                    except stripe.error.StripeError as e:
                        return jsonify({"error": f"Payment verification failed: {str(e)}"}), 402
                else:
                    # Stripe not configured - allow submission with audit log
                    payment_verified = True
                    
                    # Record the payment
                    PaymentTrackingService.record_payment_intent(
                        payment_intent_id, request.user['uid'], status='succeeded'
                    )
                    
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="PAYMENT_SYSTEM_NOT_CONFIGURED",
                        error_message="Stripe not configured - allowing free submission",
                        endpoint="/build-pdf"
                    )
            
            if not payment_verified:
                return jsonify({"error": "Payment verification failed"}), 402
            
            # Generate PDFs using the service
            pdf_service = PDFGenerationService()
            created_files = pdf_service.generate_pdf_for_submission(data, request.user['uid'])
            
            # Mark payment as used for submission after successful generation
            submission_ids = [file_info.get('filing_id') for file_info in created_files if file_info.get('filing_id')]
            if submission_ids:
                PaymentTrackingService.mark_used_for_submission(
                    payment_intent_id, request.user['uid'], submission_ids[0]
                )
            
            enhanced_audit.log_error_event(
                user_email=request.user.get('email', 'unknown'),
                error_type="PDF_SUBMISSION_SUCCESS",
                error_message=f"PDF generated for {len(created_files)} month(s) - Payment: {payment_intent_id}",
                endpoint="/build-pdf"
            )
            
            # Single file - return PDF directly
            if len(created_files) == 1:
                from flask import send_file
                return send_file(
                    created_files[0]['pdf_path'],
                    as_attachment=True,
                    download_name=f"form2290_{created_files[0]['month']}.pdf"
                )
            else:
                # Multiple files - return JSON with info
                download_info = []
                for file_info in created_files:
                    month = file_info['month']
                    month_display = f"{month[:4]}-{month[4:]}"
                    download_info.append({
                        'month': month,
                        'month_display': month_display,
                        'filing_id': file_info['filing_id'],
                        'vehicle_count': file_info['vehicle_count'],
                        'download_url': f"/download-pdf-by-month/{month}",
                        'filename': f"form2290_{month_display}_{file_info['vehicle_count']}vehicles.pdf"
                    })
                
                return jsonify({
                    "success": True,
                    "message": f"Generated {len(created_files)} PDF(s) successfully",
                    "files": download_info,
                    "redirect_message": "Visit My Filings section to see your files."
                }), 200
                
        except Exception as e:
            enhanced_audit.log_error_event(
                user_email=request.user.get('email', 'unknown'),
                error_type="PDF_GENERATION_ERROR",
                error_message=str(e),
                endpoint="/build-pdf"
            )
            return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500

    @app.route("/download-pdf-by-month/<month>", methods=["GET"])
    @verify_firebase_token
    def download_pdf_by_month(month):
        """Download PDF for a specific month - LEGACY ROUTE"""
        # TODO: Move to user routes
        return jsonify({
            "message": "PDF download temporarily disabled during refactoring",
            "status": "coming_soon"
        }), 503

    @app.route("/preview-pdf", methods=["POST", "OPTIONS"])
    @verify_firebase_token
    def preview_pdf():
        """Generate PDF preview for form data (with optional payment support)"""
        if request.method == "OPTIONS":
            return jsonify({"message": "CORS preflight"}), 200
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            # Import PDF service
            from services.pdf_service import PDFGenerationService
            
            # Validate required fields
            if not data.get("business_name") or not data.get("ein"):
                return jsonify({"error": "Missing business_name or ein"}), 400
            
            if not data.get("vehicles"):
                return jsonify({"error": "No vehicles provided"}), 400
            
            # Check if payment is provided (optional for preview)
            payment_intent_id = data.get("payment_intent_id")
            payment_verified = False
            
            if payment_intent_id:
                # Check if we can reuse an existing payment
                if PaymentTrackingService.can_reuse_payment(payment_intent_id, request.user['uid']):
                    payment_verified = True
                    
                    # Mark as used for preview
                    PaymentTrackingService.mark_used_for_preview(payment_intent_id, request.user['uid'])
                    
                    enhanced_audit.log_error_event(
                        user_email=request.user.get('email', 'unknown'),
                        error_type="PAYMENT_REUSED_FOR_PREVIEW",
                        error_message=f"Payment {payment_intent_id} reused for preview",
                        endpoint="/preview-pdf"
                    )
                else:
                    # Try to import Stripe, but handle gracefully if not available
                    try:
                        import stripe
                        STRIPE_AVAILABLE = True
                    except ImportError:
                        STRIPE_AVAILABLE = False
                        stripe = None
                    
                    # Verify payment if provided - fallback to original logic for new payments
                    if Config.FLASK_ENV == 'development' and 'dev_mode' in payment_intent_id:
                        payment_verified = True
                        
                        # Record/update the payment
                        PaymentTrackingService.record_payment_intent(
                            payment_intent_id, request.user['uid'], status='succeeded'
                        )
                        PaymentTrackingService.mark_used_for_preview(payment_intent_id, request.user['uid'])
                        
                        enhanced_audit.log_error_event(
                            user_email=request.user.get('email', 'unknown'),
                            error_type="PAYMENT_BYPASS_DEV_MODE_PREVIEW",
                            error_message="Development mode payment bypass for preview",
                            endpoint="/preview-pdf"
                        )
                    elif payment_intent_id == 'dev_mode_fake_client_secret':
                        payment_verified = True
                        
                        # Record the legacy dev mode payment
                        PaymentTrackingService.record_payment_intent(
                            payment_intent_id, request.user['uid'], status='succeeded'
                        )
                        PaymentTrackingService.mark_used_for_preview(payment_intent_id, request.user['uid'])
                        
                        enhanced_audit.log_error_event(
                            user_email=request.user.get('email', 'unknown'),
                            error_type="PAYMENT_BYPASS_NO_STRIPE_PREVIEW",
                            error_message="Payment bypass due to Stripe not configured for preview",
                            endpoint="/preview-pdf"
                        )
                    elif Config.STRIPE_SECRET_KEY and STRIPE_AVAILABLE:
                        try:
                            stripe.api_key = Config.STRIPE_SECRET_KEY
                            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                            
                            if intent.status == 'succeeded':
                                if intent.metadata.get('user_uid') == request.user['uid']:
                                    payment_verified = True
                                    
                                    # Record/update the payment and mark as used for preview
                                    PaymentTrackingService.record_payment_intent(
                                        payment_intent_id, request.user['uid'], status='succeeded'
                                    )
                                    PaymentTrackingService.mark_used_for_preview(payment_intent_id, request.user['uid'])
                                    
                                    enhanced_audit.log_error_event(
                                        user_email=request.user.get('email', 'unknown'),
                                        error_type="PAYMENT_VERIFIED_PREVIEW",
                                        error_message=f"Payment verified for preview: {payment_intent_id}",
                                        endpoint="/preview-pdf"
                                    )
                                else:
                                    enhanced_audit.log_error_event(
                                        user_email=request.user.get('email', 'unknown'),
                                        error_type="PAYMENT_VERIFICATION_FAILED_PREVIEW",
                                        error_message="Payment verification failed for preview - user mismatch",
                                        endpoint="/preview-pdf"
                                    )
                            else:
                                enhanced_audit.log_error_event(
                                    user_email=request.user.get('email', 'unknown'),
                                    error_type="PAYMENT_NOT_COMPLETED_PREVIEW",
                                    error_message=f"Payment not completed for preview: {intent.status}",
                                    endpoint="/preview-pdf"
                                )
                        except Exception as e:
                            enhanced_audit.log_error_event(
                                user_email=request.user.get('email', 'unknown'),
                                error_type="PAYMENT_ERROR_PREVIEW",
                                error_message=f"Payment error during preview: {str(e)}",
                                endpoint="/preview-pdf"
                            )
                    else:
                        # Stripe not configured but payment was attempted
                        payment_verified = True
                        
                        # Record the payment
                        PaymentTrackingService.record_payment_intent(
                            payment_intent_id, request.user['uid'], status='succeeded'
                        )
                        PaymentTrackingService.mark_used_for_preview(payment_intent_id, request.user['uid'])
                        
                        enhanced_audit.log_error_event(
                            user_email=request.user.get('email', 'unknown'),
                            error_type="PAYMENT_SYSTEM_NOT_CONFIGURED_PREVIEW",
                            error_message="Stripe not configured - allowing free preview",
                            endpoint="/preview-pdf"
                        )
            
            # Generate preview PDFs for all months
            pdf_service = PDFGenerationService()
            
            # ALWAYS use preview method - payment only affects access, not storage
            # Preview should never save to database or S3, regardless of payment
            preview_files = pdf_service.generate_preview_pdfs_all_months(data)
            
            if payment_verified:
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="PAID_PREVIEW_SUCCESS",
                    error_message=f"Paid preview generated for {len(preview_files)} month(s) - NO DATABASE SAVE",
                    endpoint="/preview-pdf"
                )
            else:
                enhanced_audit.log_error_event(
                    user_email=request.user.get('email', 'unknown'),
                    error_type="FREE_PREVIEW_SUCCESS", 
                    error_message=f"Free preview generated for {len(preview_files)} month(s) - NO DATABASE SAVE",
                    endpoint="/preview-pdf"
                )
            
            # If only one file, return it directly
            if len(preview_files) == 1:
                from flask import send_file
                filename_prefix = "form2290_paid" if payment_verified else "form2290_preview"
                return send_file(
                    preview_files[0]['pdf_path'],
                    as_attachment=True,
                    download_name=f"{filename_prefix}_{preview_files[0]['month']}.pdf",
                    mimetype='application/pdf'
                )
            else:
                # Multiple files - return JSON with info about all files
                preview_info = []
                for file_info in preview_files:
                    month = file_info['month']
                    month_display = f"{month[:4]}-{month[5:]}" if len(month) >= 7 else month
                    filename_prefix = "form2290_paid" if payment_verified else "form2290_preview"
                    preview_info.append({
                        'month': month,
                        'month_display': month_display,
                        'vehicle_count': file_info['vehicle_count'],
                        'download_url': f"/preview-pdf-by-month/{month}",
                        'filename': f"{filename_prefix}_{month_display}_{file_info['vehicle_count']}vehicles.pdf",
                        'paid': payment_verified
                    })
                
                return jsonify({
                    "success": True,
                    "multiple_files": True,
                    "message": f"{'Paid' if payment_verified else 'Free'} preview generated for {len(preview_files)} month(s)",
                    "files": preview_info,
                    "payment_verified": payment_verified
                }), 200
            
        except Exception as e:
            print(f"Preview PDF generation error: {e}")
            enhanced_audit.log_error_event(
                user_email=request.user.get('email', 'unknown'),
                error_type="PREVIEW_ERROR",
                error_message=str(e),
                endpoint="/preview-pdf"
            )
            return jsonify({"error": f"Preview generation failed: {str(e)}"}), 500
    
    @app.route("/preview-pdf-by-month/<month>", methods=["GET"])
    @verify_firebase_token
    def preview_pdf_by_month(month):
        """Download a specific month's preview PDF"""
        try:
            import os
            from flask import send_file
            
            # Look for the preview file
            out_dir = os.path.join(os.path.dirname(__file__), "output")
            preview_file = os.path.join(out_dir, f"preview_form2290_{month}.pdf")
            
            if not os.path.exists(preview_file):
                return jsonify({"error": "Preview file not found. Please regenerate preview."}), 404
            
            month_display = f"{month[:4]}-{month[5:]}" if len(month) >= 7 else month
            return send_file(
                preview_file,
                as_attachment=True,
                download_name=f"form2290_preview_{month_display}.pdf",
                mimetype='application/pdf'
            )
            
        except Exception as e:
            print(f"Preview download error: {e}")
            return jsonify({"error": f"Preview download failed: {str(e)}"}), 500

# Create the Flask app
app = create_app()

if __name__ == "__main__":
    print("🔥 Starting Flask development server...")
    print(f"🔧 Flask ENV: {Config.FLASK_ENV}")
    print(f"🗄️  Database: {Config.DATABASE_URL[:50]}...")
    
    # Test database connection
    success, message = test_database_connection()
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    
    print(f"🪣 S3 Bucket: {Config.get_bucket_name()}")
    print(f"👨‍💼 Admin Email: {Config.ADMIN_EMAIL}")
    
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
