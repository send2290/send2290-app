import logging
import hashlib
import os
from datetime import datetime
from flask import request

class IRS2290AuditLogger:
    def __init__(self, environment='local'):
        """
        Enhanced audit logger with comprehensive tracking for IRS 2290 application
        environment: 'local' or 'production'
        """
        self.environment = environment
        
        # Simple file naming with absolute paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Get backend directory
        if environment == 'production':
            log_filename = os.path.join(base_dir, 'Audit', 'productionaudit.log')
            logger_name = 'PRODUCTION_AUDIT'
        else:
            log_filename = os.path.join(base_dir, 'Audit', 'localaudit.log')
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
    
    def log_login_attempt(self, email, success=True, failure_reason=None):
        """Log user login attempts"""
        status = "SUCCESS" if success else "FAILED"
        details = {
            'email': email,
            'ip_address': self.get_client_ip(),
            'user_agent': self.get_user_agent(),
            'environment': self.environment
        }
        
        if not success and failure_reason:
            details['failure_reason'] = failure_reason
            
        log_entry = f"LOGIN_ATTEMPT: {status} | USER: {email} | ENV: {self.environment} | IP: {self.get_client_ip()}"
        if failure_reason:
            log_entry += f" | REASON: {failure_reason}"
            
        self.logger.info(log_entry)
    
    def log_logout(self, email):
        """Log user logout"""
        log_entry = f"LOGOUT: USER: {email} | ENV: {self.environment} | IP: {self.get_client_ip()}"
        self.logger.info(log_entry)
    
    def log_form_submission(self, user_email, ein, tax_year, month, vehicle_count, submission_id=None):
        """Log Form 2290 submissions"""
        details = {
            'ein': ein,
            'tax_year': tax_year,
            'month': month,
            'vehicle_count': vehicle_count,
            'ip_address': self.get_client_ip(),
            'submission_id': submission_id
        }
        
        log_entry = f"FORM_SUBMISSION: USER: {user_email} | EIN: {ein} | MONTH: {month} | VEHICLES: {vehicle_count} | ENV: {self.environment}"
        if submission_id:
            log_entry += f" | SUBMISSION_ID: {submission_id}"
            
        self.logger.info(log_entry)
    
    def log_document_access(self, user_email, action, document_type, document_id=None, ein=None):
        """Log document downloads, views, or deletions"""
        details = {
            'action': action,  # DOWNLOAD, VIEW, DELETE
            'document_type': document_type,  # XML, PDF
            'document_id': document_id,
            'ein': ein,
            'ip_address': self.get_client_ip()
        }
        
        log_entry = f"DOCUMENT_ACCESS: {action} | USER: {user_email} | TYPE: {document_type} | ENV: {self.environment}"
        if document_id:
            log_entry += f" | DOC_ID: {document_id}"
        if ein:
            log_entry += f" | EIN: {ein}"
            
        self.logger.info(log_entry)
    
    def log_account_settings_change(self, user_email, setting_changed, old_value=None, new_value=None):
        """Log account settings changes"""
        details = {
            'setting': setting_changed,
            'ip_address': self.get_client_ip(),
            'user_agent': self.get_user_agent()
        }
        
        # Don't log sensitive values in plain text
        if old_value and setting_changed.lower() not in ['password', 'token', 'secret']:
            details['old_value'] = old_value
        if new_value and setting_changed.lower() not in ['password', 'token', 'secret']:
            details['new_value'] = new_value
            
        log_entry = f"SETTINGS_CHANGE: {setting_changed} | USER: {user_email} | ENV: {self.environment} | IP: {self.get_client_ip()}"
        self.logger.info(log_entry)
    
    def log_data_access(self, user_email, action, data_type, record_count=None, filters=None):
        """Log data access operations (viewing lists, searching, etc.)"""
        details = {
            'action': action,  # VIEW_LIST, SEARCH, FILTER
            'data_type': data_type,  # SUBMISSIONS, DOCUMENTS, USERS
            'record_count': record_count,
            'ip_address': self.get_client_ip()
        }
        
        if filters:
            details['filters'] = str(filters)
            
        log_entry = f"DATA_ACCESS: {action} | USER: {user_email} | TYPE: {data_type} | ENV: {self.environment}"
        if record_count:
            log_entry += f" | RECORDS: {record_count}"
            
        self.logger.info(log_entry)
    
    def log_error_event(self, user_email, error_type, error_message, endpoint=None):
        """Log application errors and exceptions"""
        details = {
            'error_type': error_type,
            'endpoint': endpoint or request.endpoint if request else 'Unknown',
            'ip_address': self.get_client_ip(),
            'user_agent': self.get_user_agent()
        }
        
        log_entry = f"ERROR_EVENT: {error_type} | USER: {user_email} | ENV: {self.environment} | MSG: {error_message}"
        if endpoint:
            log_entry += f" | ENDPOINT: {endpoint}"
            
        self.logger.error(log_entry)
    
    def log_security_event(self, event_type, user_email=None, details=None):
        """Log security-related events"""
        log_entry = f"SECURITY_EVENT: {event_type} | ENV: {self.environment} | IP: {self.get_client_ip()}"
        if user_email:
            log_entry += f" | USER: {user_email}"
        if details:
            log_entry += f" | DETAILS: {details}"
            
        self.logger.warning(log_entry)
    
    def log_api_usage(self, user_email, endpoint, method, response_status, response_time_ms=None):
        """Log API endpoint usage for monitoring"""
        details = {
            'endpoint': endpoint,
            'method': method,
            'status': response_status,
            'ip_address': self.get_client_ip(),
            'user_agent': self.get_user_agent()
        }
        
        if response_time_ms:
            details['response_time_ms'] = response_time_ms
            
        log_entry = f"API_USAGE: {method} {endpoint} | USER: {user_email} | STATUS: {response_status} | ENV: {self.environment}"
        if response_time_ms:
            log_entry += f" | TIME: {response_time_ms}ms"
            
        self.logger.info(log_entry)
    
    def get_user_agent(self):
        """Get user agent from request"""
        try:
            return request.headers.get('User-Agent', 'Unknown')[:200]  # Limit length
        except:
            return 'Unknown'