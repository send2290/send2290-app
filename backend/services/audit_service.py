"""Audit logging service"""
import logging
import datetime
import os
from config import Config

# Setup audit logger
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# Create audit log handler if not exists
if not audit_logger.handlers:
    audit_handler = logging.FileHandler(Config.AUDIT_LOG_FILE)
    audit_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)

def log_admin_action(action, details):
    """Log admin actions for audit trail"""
    audit_logger.info(f"ADMIN_ACTION: {action} - {details}")

def log_error_event(user_email, error_type, error_message, endpoint):
    """Log error events for debugging and audit"""
    audit_logger.error(f"ERROR: {error_type} - User: {user_email} - Endpoint: {endpoint} - Message: {error_message}")

def init_audit_logging():
    """Initialize audit logging system"""
    try:
        # Ensure audit log file exists
        if not os.path.exists(Config.AUDIT_LOG_FILE):
            with open(Config.AUDIT_LOG_FILE, 'w') as f:
                f.write(f"# Audit log initialized at {datetime.datetime.utcnow().isoformat()}\n")
        
        audit_logger.info("Audit logging system initialized")
        return True
    except Exception as e:
        print(f"Failed to initialize audit logging: {e}")
        return False
