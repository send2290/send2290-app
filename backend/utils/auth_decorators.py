"""Authentication decorators for Flask routes"""
from functools import wraps
from flask import request, jsonify, make_response
import firebase_admin
from firebase_admin import auth
from config import Config

def verify_firebase_token(f):
    """Decorator to verify Firebase authentication token"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return make_response("", 200)
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "Authorization header missing", 
                "message": "Please sign in to submit your form. Your account will be created automatically if needed."
            }), 401
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded = auth.verify_id_token(token)
            request.user = decoded
        except Exception as e:
            return jsonify({"error": "Invalid token", "details": str(e)}), 403
        
        return f(*args, **kwargs)
    return wrapper

def verify_admin_token(f):
    """Decorator to verify admin authentication token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Import audit logging here to avoid circular imports
        try:
            from services.audit_service import log_admin_action
        except ImportError:
            # Fallback if audit service not available yet
            def log_admin_action(action, details):
                print(f"AUDIT: {action} - {details}")
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", "No valid Bearer token")
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            admin_emails = [Config.ADMIN_EMAIL, 'admin@send2290.com']
            
            if decoded_token.get('email') not in admin_emails:
                log_admin_action("UNAUTHORIZED_ACCESS_ATTEMPT", 
                               f"Non-admin user {decoded_token.get('email')}")
                return jsonify({'error': 'Admin access required'}), 403
            
            request.user = decoded_token
            return f(*args, **kwargs)
        except Exception as e:
            log_admin_action("INVALID_TOKEN_ATTEMPT", f"Invalid token: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
    return decorated
