#!/usr/bin/env python3
"""
Script to fetch production audit logs from live server
"""
import requests
import sys
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Production API URL
PRODUCTION_API = "https://send2290-app.onrender.com"

# Get admin token from environment variable
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN')
if not ADMIN_TOKEN:
    print("❌ Error: ADMIN_TOKEN not found in .env file")
    print("Please add ADMIN_TOKEN=your_token_here to your .env file")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {ADMIN_TOKEN}"
}

def fetch_production_logs(lines=50):
    """Fetch production audit logs from live server"""
    print(f"🌍 Fetching production audit logs from {PRODUCTION_API}")
    
    url = f"{PRODUCTION_API}/admin/audit-logs/production"
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            logs = data.get('logs', [])
            
            print(f"\n📋 Production Audit Logs (Last {len(logs)} entries):")
            print("=" * 80)
            
            for log_line in logs:
                print(log_line.rstrip())
            
            print("=" * 80)
            print(f"Total lines in production log: {data.get('total_lines', 'Unknown')}")
            print(f"Showing last: {len(logs)}")
            
            # Save to local file for reference
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local_filename = f"production_audit_backup_{timestamp}.log"
            
            with open(local_filename, 'w') as f:
                for log_line in logs:
                    f.write(log_line)
            
            print(f"\n💾 Saved to local file: {local_filename}")
            
        elif resp.status_code == 404:
            print("❌ Production audit log file not found on server")
            print("This could mean:")
            print("  1. No production activities have been logged yet")
            print("  2. The production audit logger isn't working")
            print("  3. The endpoint isn't deployed yet")
        else:
            print(f"❌ Failed to fetch logs: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"❌ Error fetching production logs: {e}")

def download_production_logs():
    """Download the complete production audit log file"""
    print(f"📥 Downloading complete production audit log from {PRODUCTION_API}")
    
    url = f"{PRODUCTION_API}/admin/audit-logs/production/download"
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"production_audit_complete_{timestamp}.log"
            
            with open(filename, 'wb') as f:
                f.write(resp.content)
            
            print(f"✅ Downloaded complete production audit log to: {filename}")
        else:
            print(f"❌ Failed to download: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"❌ Error downloading production logs: {e}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--download':
        download_production_logs()
    else:
        lines = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 50
        fetch_production_logs(lines)

if __name__ == "__main__":
    print("🔍 Production Audit Log Fetcher")
    print("Usage:")
    print("  python fetch_production_logs.py [lines]     # View recent logs")
    print("  python fetch_production_logs.py --download  # Download complete log")
    print()
    main()
