#!/usr/bin/env python3
"""
Clear database tables - with option for production
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def clear_database(use_production=False):
    if use_production:
        DATABASE_URL = os.getenv('DATABASE_URL')  # PostgreSQL production
        print("🚀 PRODUCTION mode: Using PostgreSQL database")
        print("⚠️  WARNING: This will clear your LIVE/PRODUCTION database!")
        
        confirm = input("Are you sure you want to clear PRODUCTION database? Type 'YES' to confirm: ")
        if confirm != 'YES':
            print("❌ Operation cancelled")
            return False
    else:
        DATABASE_URL = "sqlite:///./send2290.db"  # Local SQLite
        print("🔧 Development mode: Using SQLite database")

    if not DATABASE_URL:
        print("❌ DATABASE_URL not found!")
        return False

    print(f"📍 Database URL: {DATABASE_URL[:50]}...")

    engine = create_engine(DATABASE_URL, echo=False)

    print("\n🗑️  Clearing database tables...")

    try:
        with engine.connect() as conn:
            # Clear filings_documents table first (foreign key constraint)
            result = conn.execute(text("DELETE FROM filings_documents"))
            print(f"✅ Deleted {result.rowcount} records from filings_documents table")
            
            # Clear submissions table
            result = conn.execute(text("DELETE FROM submissions"))
            print(f"✅ Deleted {result.rowcount} records from submissions table")
            
            # Reset auto-increment counters (SQLite specific)
            if "sqlite" in DATABASE_URL:
                try:
                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name='submissions'"))
                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name='filings_documents'"))
                    print("✅ Reset auto-increment counters")
                except:
                    print("ℹ️  Auto-increment counters not reset (not needed)")
            
            conn.commit()
            print("\n🎉 Database cleared successfully!")
            
            # Verify tables are empty
            submissions_count = conn.execute(text("SELECT COUNT(*) FROM submissions")).scalar()
            documents_count = conn.execute(text("SELECT COUNT(*) FROM filings_documents")).scalar()
            
            print(f"\n📊 Verification:")
            print(f"   Submissions: {submissions_count}")
            print(f"   Documents: {documents_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--production":
        clear_database(use_production=True)
    else:
        print("Usage:")
        print("  python clear_database.py              # Clear local database")
        print("  python clear_database.py --production # Clear production database")
        print()
        choice = input("Clear (l)ocal or (p)roduction database? [l/p]: ").lower()
        if choice == 'p':
            clear_database(use_production=True)
        else:
            clear_database(use_production=False)
