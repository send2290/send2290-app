import os
from dotenv import load_dotenv

# Load environment variables from both root and backend .env files
# Root .env first (for NODE_ENV), then backend .env (for other settings)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))  # Root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))        # Backend .env

class Config:
    """Application configuration class"""
    
    # Environment Configuration - Use NODE_ENV from root .env as primary control
    NODE_ENV = os.getenv("NODE_ENV", "development")
    FLASK_ENV = NODE_ENV  # Keep FLASK_ENV for compatibility, but derive from NODE_ENV
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Database Configuration - Switch based on NODE_ENV
    DATABASE_URL = ("sqlite:///./send2290.db" if NODE_ENV == "development" 
                   else os.getenv('DATABASE_URL'))
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    FILES_BUCKET = os.getenv('FILES_BUCKET')
    BUCKET = os.getenv('BUCKET')  # Keep both for compatibility
    
    # Firebase Configuration
    FIREBASE_ADMIN_KEY_JSON = os.getenv('FIREBASE_ADMIN_KEY_JSON')
    
    # Stripe Configuration
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
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
