"""Database models and setup"""
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config

# Database setup
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Submission(Base):
    """Model for form submissions"""
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_uid = Column(String, index=True)
    month = Column(String, index=True)
    xml_s3_key = Column(String)
    pdf_s3_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    form_data = Column(Text)

class FilingsDocument(Base):
    """Model for filing documents"""
    __tablename__ = 'filings_documents'
    
    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, index=True)
    user_uid = Column(String, index=True)
    document_type = Column(String)
    s3_key = Column(String)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

class PaymentIntent(Base):
    """Model for tracking payment intents and their usage"""
    __tablename__ = 'payment_intents'
    
    id = Column(Integer, primary_key=True, index=True)
    payment_intent_id = Column(String, unique=True, index=True)  # Stripe payment intent ID or dev mode ID
    user_uid = Column(String, index=True)
    amount_cents = Column(Integer)  # Amount in cents (e.g., 4500 for $45.00)
    status = Column(String)  # 'succeeded', 'pending', 'failed'
    used_for_preview = Column(String, default='false')  # 'true' or 'false' - track if used for preview
    used_for_submission = Column(String, default='false')  # 'true' or 'false' - track if used for submission
    submission_id = Column(Integer, nullable=True)  # Link to submission if used for actual submission
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_database_connection():
    """Test database connectivity"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {e}"
