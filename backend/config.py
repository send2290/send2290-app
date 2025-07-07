import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration class"""
    
    # Flask Configuration
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Database Configuration
    DATABASE_URL = ("sqlite:///./send2290.db" if FLASK_ENV == "development" 
                   else os.getenv('DATABASE_URL'))
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    FILES_BUCKET = os.getenv('FILES_BUCKET')
    BUCKET = os.getenv('BUCKET')  # Keep both for compatibility
    
    # Firebase Configuration
    FIREBASE_ADMIN_KEY_JSON = os.getenv('FIREBASE_ADMIN_KEY_JSON')
    
    # Admin Configuration
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@send2290.com')
    
    # CORS Configuration
    CORS_CONFIG = {
        "resources": {r"/*": {"origins": [
            "http://localhost:3000",
            "http://localhost:3001", 
            "https://send2290.com",
            "https://www.send2290.com"
        ]}},
        "methods": ["GET", "POST", "OPTIONS", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
    
    # File paths
    FORM_POSITIONS_FILE = "form_positions.json"
    TEMPLATE_PDF_FILE = "f2290_template.pdf"
    AUDIT_LOG_FILE = "audit.log"
    
    @classmethod
    def get_bucket_name(cls):
        """Get the appropriate bucket name (handles both BUCKET and FILES_BUCKET)"""
        return cls.BUCKET or cls.FILES_BUCKET
