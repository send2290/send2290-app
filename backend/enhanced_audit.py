import logging
import hashlib
import os
from datetime import datetime
from flask import request

class IRS2290AuditLogger:
    def __init__(self, environment='local'):
        """
        Simple audit logger with clear environment separation
        environment: 'local' or 'production'
        """
        self.environment = environment
        
        # Simple file naming
        if environment == 'production':
            log_filename = 'productionaudit.log'
            logger_name = 'PRODUCTION_AUDIT'
        else:
            log_filename = 'localaudit.log'
            logger_name = 'LOCAL_AUDIT'
            
        self.logger = logging.getLogger(logger_name)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.FileHandler(log_filename)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def get_client_ip(self):
        try:
            return request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'Unknown'))
        except:
            return 'Unknown'
    
    def log_user_action(self, user_id, action, form_data=None, ein=None, tax_year=None):
        """Log user actions (form submissions, etc.)"""
        details = {
            'environment': self.environment,
            'user_id': user_id,
            'action': action,
            'timestamp': datetime.utcnow().isoformat(),
            'ein': ein,
            'tax_year': tax_year,
            'ip_address': self.get_client_ip()
        }
        
        if form_data and ein:
            # Only hash if we have actual form data
            details['data_hash'] = hashlib.sha256(str(form_data).encode()).hexdigest()[:16]
            
        self.logger.info(f"USER_ACTION: {action} | DETAILS: {details}")
    
    def log_admin_action(self, user_email, action, details):
        """Log admin actions"""
        log_entry = f"ADMIN_ACTION: {action} | USER: {user_email} | ENV: {self.environment} | DETAILS: {details}"
        self.logger.info(log_entry)