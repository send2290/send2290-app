#!/usr/bin/env python3
"""
Admin token management utility
"""
import os
import sys
from dotenv import load_dotenv, set_key, find_dotenv

def check_token():
    """Check if admin token exists and is valid format"""
    load_dotenv()
    
    token = os.getenv('ADMIN_TOKEN')
    if not token:
        print("❌ ADMIN_TOKEN not found in .env file")
        return False
    
    # Basic JWT format check (3 parts separated by dots)
    parts = token.split('.')
    if len(parts) != 3:
        print("❌ ADMIN_TOKEN appears to be invalid format (not a JWT)")
        return False
    
    print("✅ ADMIN_TOKEN found and appears to be valid format")
    print(f"Token preview: {token[:20]}...{token[-20:]}")
    return True

def update_token(new_token):
    """Update the admin token in .env file"""
    env_file = find_dotenv()
    if not env_file:
        env_file = '.env'
    
    # Basic validation
    if not new_token or len(new_token.split('.')) != 3:
        print("❌ Invalid token format. JWT tokens should have 3 parts separated by dots.")
        return False
    
    try:
        set_key(env_file, 'ADMIN_TOKEN', new_token)
        print(f"✅ ADMIN_TOKEN updated in {env_file}")
        print(f"New token preview: {new_token[:20]}...{new_token[-20:]}")
        return True
    except Exception as e:
        print(f"❌ Failed to update token: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("🔑 Admin Token Management")
        print("Usage:")
        print("  python token_manager.py check                    # Check current token")
        print("  python token_manager.py update <new_token>       # Update token")
        print("  python token_manager.py rotate                   # Instructions for token rotation")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'check':
        check_token()
    elif command == 'update' and len(sys.argv) > 2:
        new_token = sys.argv[2]
        update_token(new_token)
    elif command == 'rotate':
        print("🔄 Token Rotation Instructions:")
        print("1. Go to your Firebase Console → Authentication → Users")
        print("2. Generate a new ID token for your admin user")
        print("3. Copy the new token")
        print("4. Run: python token_manager.py update <new_token>")
        print("5. Test with: python admin_delete_submissions.py --env local")
        print("6. Deploy updated .env to production")
        print("\n⚠️  Remember: Firebase ID tokens expire (usually 1 hour)")
        print("   For production, consider using Firebase Admin SDK service account")
    else:
        print("❌ Invalid command. Use 'check', 'update <token>', or 'rotate'")

if __name__ == "__main__":
    main()
