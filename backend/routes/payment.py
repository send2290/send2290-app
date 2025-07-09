"""Payment routes for Stripe integration"""
import json
from flask import Blueprint, request, jsonify
from config import Config
from utils.auth_decorators import verify_firebase_token
from models import SessionLocal, Submission
from services.audit_service import log_admin_action

# Try to import Stripe, but don't fail if it's not available
try:
    import stripe
    STRIPE_AVAILABLE = True
    print("✅ Stripe module loaded successfully")
except ImportError as e:
    STRIPE_AVAILABLE = False
    print(f"⚠️ WARNING: Stripe module not available: {e}")

payment_bp = Blueprint('payment', __name__)

FORM_SUBMISSION_PRICE = 4500  # $45.00 in cents

@payment_bp.route('/config', methods=['GET'])
def get_stripe_config():
    """Get Stripe publishable key for frontend"""
    print("🔍 DEBUG: Config route called")
    
    # Always return development config for now
    return jsonify({
        'publishableKey': 'pk_dev_mode_testing',
        'price': FORM_SUBMISSION_PRICE,
        'dev_mode': True
    })

@payment_bp.route('/create-payment-intent', methods=['POST'])
@verify_firebase_token
def create_payment_intent():
    """Create a Stripe Payment Intent for form submission"""
    print("🔍 DEBUG: Payment intent route called")
    
    try:
        # Always return development mode for now
        return jsonify({
            'client_secret': 'dev_mode_fake_client_secret',
            'amount': FORM_SUBMISSION_PRICE,
            'dev_mode': True
        })
        
    except Exception as e:
        print(f"🔍 DEBUG: Error in create_payment_intent: {str(e)}")
        return jsonify({'error': f'Payment intent creation failed: {str(e)}'}), 500

# Temporarily disabled other routes to debug
"""
@payment_bp.route('/confirm-payment', methods=['POST'])
@verify_firebase_token  
def confirm_payment():
    # Always return success for dev mode
    return jsonify({
        'success': True,
        'payment_intent_id': 'dev_mode_fake_client_secret',
        'amount_received': FORM_SUBMISSION_PRICE,
        'dev_mode': True
    })

@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    # Webhook placeholder
    return jsonify({'status': 'success'})
"""

@payment_bp.route('/test', methods=['GET'])
def test_payment_route():
    """Test endpoint to verify payment routes are working"""
    return jsonify({
        'status': 'Payment routes are working',
        'flask_env': Config.FLASK_ENV,
        'stripe_configured': bool(Config.STRIPE_SECRET_KEY),
        'dev_mode': Config.FLASK_ENV == 'development' and not Config.STRIPE_SECRET_KEY
    })
