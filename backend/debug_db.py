#!/usr/bin/env python3
"""
AWS RDS Database Verification Script for Form 2290 Application
This script checks if your PostgreSQL database on AWS RDS is properly configured.
"""

import os
import sys
import psycopg2
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import datetime
from flask import request, jsonify

# Add current directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import Base, Submission, FilingsDocument
except ImportError as e:
    print(f"❌ Cannot import app modules: {e}")
    sys.exit(1)

def test_database_connection():
    """Test basic database connectivity"""
    print("=== AWS RDS PostgreSQL Database Verification ===\n")
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set!")
        print("Make sure to set your AWS RDS connection string.")
        return False
    
    # Mask password in URL for display
    display_url = database_url
    if '@' in database_url:
        parts = database_url.split('@')
        if len(parts) == 2:
            user_part = parts[0].split('://')[-1]
            if ':' in user_part:
                user, _ = user_part.split(':', 1)
                display_url = database_url.replace(user_part, f"{user}:****")
    
    print(f"📍 Database URL: {display_url}")
    
    try:
        # Test with SQLAlchemy engine
        engine = create_engine(database_url, echo=False)
        print("✅ SQLAlchemy engine created successfully")
        
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Database connection successful")
            print(f"📊 PostgreSQL Version: {version}")
            
        return engine
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return None

def check_database_schema(engine):
    """Check if all required tables and columns exist"""
    print("\n=== Database Schema Verification ===")
    
    try:
        inspector = inspect(engine)
        
        # Get all tables
        tables = inspector.get_table_names()
        print(f"📋 Existing tables: {tables}")
        
        # Check required tables
        required_tables = {
            'submissions': [
                'id', 'user_uid', 'month', 'xml_s3_key', 
                'pdf_s3_key', 'created_at', 'form_data'
            ],
            'filings_documents': [
                'id', 'filing_id', 'user_uid', 'document_type', 
                's3_key', 'uploaded_at'
            ]
        }
        
        schema_issues = []
        
        for table_name, required_columns in required_tables.items():
            if table_name not in tables:
                schema_issues.append(f"Missing table: {table_name}")
                print(f"❌ Table '{table_name}' not found")
            else:
                print(f"✅ Table '{table_name}' exists")
                
                # Check columns
                columns = [col['name'] for col in inspector.get_columns(table_name)]
                print(f"   Columns: {columns}")
                
                missing_columns = [col for col in required_columns if col not in columns]
                if missing_columns:
                    schema_issues.append(f"Table '{table_name}' missing columns: {missing_columns}")
                    print(f"   ❌ Missing columns: {missing_columns}")
                else:
                    print(f"   ✅ All required columns present")
        
        # Check for Alembic version table
        if 'alembic_version' in tables:
            print("✅ Alembic version table exists")
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.fetchone()
                if version:
                    print(f"   Current migration: {version[0]}")
                else:
                    print("   ⚠️  No migration version recorded")
        else:
            schema_issues.append("Missing alembic_version table")
            print("❌ Alembic version table not found")
        
        return len(schema_issues) == 0, schema_issues
        
    except Exception as e:
        print(f"❌ Schema check failed: {str(e)}")
        return False, [f"Schema check error: {str(e)}"]

def test_database_operations(engine):
    """Test basic database operations"""
    print("\n=== Database Operations Test ===")
    
    try:
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        try:
            # Test query operations
            submissions_count = db.query(Submission).count()
            filings_count = db.query(FilingsDocument).count()
            
            print(f"📊 Current submissions: {submissions_count}")
            print(f"📊 Current filing documents: {filings_count}")
            
            # Test insert operation
            test_submission = Submission(
                user_uid="test_verification_user",
                month="July 2024",
                xml_s3_key="test/verification.xml",
                form_data='{"test": "verification", "timestamp": "' + str(datetime.datetime.utcnow()) + '"}',
                created_at=datetime.datetime.utcnow()
            )
            
            db.add(test_submission)
            db.commit()
            db.refresh(test_submission)
            
            print(f"✅ Test submission created with ID: {test_submission.id}")
            
            # Test filing document insert
            test_filing_doc = FilingsDocument(
                filing_id=test_submission.id,
                user_uid="test_verification_user",
                document_type="xml",
                s3_key="test/verification.xml",
                uploaded_at=datetime.datetime.utcnow()
            )
            
            db.add(test_filing_doc)
            db.commit()
            
            print(f"✅ Test filing document created with ID: {test_filing_doc.id}")
            
            # Test query with join
            result = db.execute(text("""
                SELECT s.id, s.user_uid, s.month, f.document_type 
                FROM submissions s 
                JOIN filings_documents f ON s.id = f.filing_id 
                WHERE s.user_uid = 'test_verification_user'
                LIMIT 1
            """)).fetchone()
            
            if result:
                print("✅ Join query successful")
                print(f"   Result: ID={result[0]}, User={result[1]}, Month={result[2]}, DocType={result[3]}")
            
            # Clean up test data
            db.delete(test_filing_doc)
            db.delete(test_submission)
            db.commit()
            print("✅ Test data cleaned up successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Database operation failed: {str(e)}")
            db.rollback()
            return False
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Database operations test failed: {str(e)}")
        return False

def check_aws_rds_specific():
    """Check AWS RDS specific configurations"""
    print("\n=== AWS RDS Specific Checks ===")
    
    database_url = os.getenv('DATABASE_URL')
    
    # Parse the database URL to check configuration
    if 'rds.amazonaws.com' in database_url:
        print("✅ Using AWS RDS PostgreSQL")
        
        # Extract region from URL
        if '.rds.' in database_url:
            try:
                region_part = database_url.split('.rds.')[1].split('.')[0]
                print(f"📍 AWS Region: {region_part}")
            except:
                print("⚠️  Could not parse AWS region from URL")
    else:
        print("⚠️  Database URL doesn't appear to be AWS RDS")
    
    # Check SSL requirement (common for AWS RDS)
    if 'sslmode=' in database_url:
        ssl_mode = database_url.split('sslmode=')[1].split('&')[0]
        print(f"🔒 SSL Mode: {ssl_mode}")
    else:
        print("⚠️  SSL mode not specified in DATABASE_URL")
        print("   AWS RDS typically requires SSL connections")

def create_missing_tables(engine):
    """Create missing tables if needed"""
    print("\n=== Creating Missing Tables ===")
    
    try:
        print("Creating tables using SQLAlchemy metadata...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created/updated successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {str(e)}")
        return False

def debug_ip():
    """Debug endpoint to see Render's actual IP address"""
    import socket
    
    # Get the IP address Render is connecting from
    request_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # Get server's public IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "Unknown"
    
    return {
        "request_ip": request_ip,
        "server_hostname": hostname,
        "server_local_ip": local_ip,
        "render_headers": {
            "X-Forwarded-For": request.headers.get('X-Forwarded-For'),
            "X-Real-IP": request.headers.get('X-Real-IP'),
            "X-Forwarded-Proto": request.headers.get('X-Forwarded-Proto'),
            "Host": request.headers.get('Host'),
            "User-Agent": request.headers.get('User-Agent')
        }
    }

def main():
    """Main verification function"""
    print("Starting AWS RDS database verification...\n")
    
    # Step 1: Test connection
    engine = test_database_connection()
    if not engine:
        return False
    
    # Step 2: Check AWS RDS specific settings
    check_aws_rds_specific()
    
    # Step 3: Check schema
    schema_ok, schema_issues = check_database_schema(engine)
    
    if not schema_ok:
        print(f"\n⚠️  Found {len(schema_issues)} schema issues:")
        for issue in schema_issues:
            print(f"   - {issue}")
        
        print("\n🔧 Attempting to fix schema issues...")
        if create_missing_tables(engine):
            print("✅ Schema issues fixed")
            # Re-check schema
            schema_ok, schema_issues = check_database_schema(engine)
        else:
            print("❌ Could not fix schema issues")
            return False
    
    # Step 4: Test operations
    if schema_ok:
        operations_ok = test_database_operations(engine)
    else:
        operations_ok = False
    
    # Final summary
    print("\n" + "="*50)
    if schema_ok and operations_ok:
        print("🎉 DATABASE VERIFICATION SUCCESSFUL!")
        print("Your AWS RDS database is properly configured for Form 2290.")
    else:
        print("❌ DATABASE VERIFICATION FAILED!")
        print("There are issues that need to be resolved.")
    print("="*50)
    
    return schema_ok and operations_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
