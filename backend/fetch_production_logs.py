#!/usr/bin/env python3
"""
Script to fetch production audit logs from live server
"""
import requests
import sys
import json
from datetime import datetime

# Production API URL
PRODUCTION_API = "https://send2290-app.onrender.com"

# Your admin token
ADMIN_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6Ijg3NzQ4NTAwMmYwNWJlMDI2N2VmNDU5ZjViNTEzNTMzYjVjNThjMTIiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vc2VuZDIyOTAtNmMxYTUiLCJhdWQiOiJzZW5kMjI5MC02YzFhNSIsImF1dGhfdGltZSI6MTc1MTAwODg3NSwidXNlcl9pZCI6IjEySDQ3TmxwSnBmVHZ3TThqdThnYzVmSHhLRjIiLCJzdWIiOiIxMkg0N05scEpwZlR2d004anU4Z2M1Zkh4S0YyIiwiaWF0IjoxNzUxMzUyMzc5LCJleHAiOjE3NTEzNTU5NzksImVtYWlsIjoibW1vaHNpbkB1bWljaC5lZHUiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsibW1vaHNpbkB1bWljaC5lZHUiXX0sInNpZ25faW5fcHJvdmlkZXIiOiJwYXNzd29yZCJ9fQ.l_5IzC7Pz2cAM4vkDsHvjfEiuOGHPwtfOiYGwrtxgc9aTU9-s74NM2IRC6APiZsAZj3o1Lm469VOPA3SxHrYmT7Xe5k3m2WRJSuH4NGZ5o617UC8QKkGOTA8dvTfG_xzLuBpe4SPGAI8uxFkXzaxSKUkAildpUKwSPaG6sVZjsopxlQilJDpVO-_9VeCSQC6YPQv91uagrlJfh9r9QWWLMVQXOfgal1PTJjk5sAE8QRGacEy-W5DPZlDuzQ_jjORXOfSzpbZaofJ6FqPv1OcBefPXxdetN6qxq2-vTJ5i-qI4JG0xK5hGUQzVu9280eM8_pzUNTVdv5TxieUlnrGQQ"

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
