"""Miscellaneous routes (health check, test connection, etc.)"""
import datetime
from flask import Blueprint, request, jsonify, make_response

misc_bp = Blueprint('misc', __name__)

@misc_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@misc_bp.route('/test-connection', methods=['GET', 'POST', 'OPTIONS'])
def test_connection():
    """Test endpoint to verify connection"""
    if request.method == "OPTIONS":
        return make_response(jsonify({}), 200)
    
    return jsonify({
        "status": "success",
        "message": "Backend is connected and working!",
        "method": request.method,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200
