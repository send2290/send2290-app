#!/usr/bin/env python3
"""
Test script to verify .env file loading
"""
import os

def load_env_vars():
    """Load environment variables from .env file"""
    env_vars = {}
    env_paths = [
        ".env",
        "backend/.env",
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "backend", ".env")
    ]
    
    print("🔍 Looking for .env files in:")
    for env_path in env_paths:
        print(f"  - {env_path}: {'✅ Found' if os.path.exists(env_path) else '❌ Not found'}")
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            print(f"\n📄 Loading from: {env_path}")
            try:
                with open(env_path, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            env_vars[key] = value
                            if key == 'ADMIN_EMAIL':
                                print(f"  ✅ Found ADMIN_EMAIL on line {line_num}: {value}")
                break
            except Exception as e:
                print(f"❌ Error reading {env_path}: {e}")
    
    return env_vars

def main():
    print("🧪 Environment Variable Test")
    print("=" * 40)
    
    env_vars = load_env_vars()
    admin_email = env_vars.get('ADMIN_EMAIL', 'NOT_FOUND')
    
    print(f"\n📧 Admin Email: {admin_email}")
    
    if admin_email == 'NOT_FOUND':
        print("❌ ADMIN_EMAIL not found in .env file")
        print("\n💡 Make sure your .env file contains:")
        print("   ADMIN_EMAIL=your-email@example.com")
    else:
        print("✅ ADMIN_EMAIL loaded successfully!")
        print("\n🔧 The notification script will use this email for:")
        print("  - Sending notifications from this address")
        print("  - Receiving notifications at this address")

if __name__ == "__main__":
    main()
