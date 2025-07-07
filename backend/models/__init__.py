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
