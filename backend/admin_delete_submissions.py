import requests
import argparse
import sys
import os

# Determine which environment we're hitting
API_BASE = "https://send2290-app.onrender.com"  # Production
# API_BASE = "http://localhost:5000"  # Uncomment for local

ADMIN_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6Ijg3NzQ4NTAwMmYwNWJlMDI2N2VmNDU5ZjViNTEzNTMzYjVjNThjMTIiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vc2VuZDIyOTAtNmMxYTUiLCJhdWQiOiJzZW5kMjI5MC02YzFhNSIsImF1dGhfdGltZSI6MTc1MTAwODg3NSwidXNlcl9pZCI6IjEySDQ3TmxwSnBmVHZ3TThqdThnYzVmSHhLRjIiLCJzdWIiOiIxMkg0N05scEpwZlR2d004anU4Z2M1Zkh4S0YyIiwiaWF0IjoxNzUxMzUyMzc5LCJleHAiOjE3NTEzNTU5NzksImVtYWlsIjoibW1vaHNpbkB1bWljaC5lZHUiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsibW1vaHNpbkB1bWljaC5lZHUiXX0sInNpZ25faW5fcHJvdmlkZXIiOiJwYXNzd29yZCJ9fQ.l_5IzC7Pz2cAM4vkDsHvjfEiuOGHPwtfOiYGwrtxgc9aTU9-s74NM2IRC6APiZsAZj3o1Lm469VOPA3SxHrYmT7Xe5k3m2WRJSuH4NGZ5o617UC8QKkGOTA8dvTfG_xzLuBpe4SPGAI8uxFkXzaxSKUkAildpUKwSPaG6sVZjsopxlQilJDpVO-_9VeCSQC6YPQv91uagrlJfh9r9QWWLMVQXOfgal1PTJjk5sAE8QRGacEy-W5DPZlDuzQ_jjORXOfSzpbZaofJ6FqPv1OcBefPXxdetN6qxq2-vTJ5i-qI4JG0xK5hGUQzVu9280eM8_pzUNTVdv5TxieUlnrGQQ"

headers = {
    "Authorization": f"Bearer {ADMIN_TOKEN}"
}

def get_environment():
    """Determine which environment we're targeting"""
    if "localhost" in API_BASE:
        return "LOCAL"
    else:
        return "PRODUCTION"

def list_submissions():
    env = get_environment()
    print(f"\n🌍 Targeting: {env} Environment ({API_BASE})")
    
    url = f"{API_BASE}/admin/submissions"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch submissions: {resp.status_code}")
        print(resp.text)
        sys.exit(1)
    submissions = resp.json()
    # Handle dict response with 'submissions' key
    if isinstance(submissions, dict) and 'submissions' in submissions:
        submissions = submissions['submissions']
    if not submissions:
        print("No submissions found.")
        sys.exit(0)
    print(f"\nAvailable Submissions in {env}:")
    ids = []
    for sub in submissions:
        if isinstance(sub, dict):
            print(f"ID: {sub.get('id')} | User: {sub.get('user_id', 'N/A')} | Timestamp: {sub.get('created_at', 'N/A')}")
            ids.append(sub.get('id'))
        else:
            print(f"ID: {sub}")
            ids.append(sub)
    return ids

def delete_single(submission_id):
    env = get_environment()
    url = f"{API_BASE}/admin/submissions/{submission_id}"
    resp = requests.delete(url, headers=headers)
    print(f"🗑️  DELETE {env} - {url} -> {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

def bulk_delete(ids):
    env = get_environment()
    url = f"{API_BASE}/admin/bulk-delete"
    data = {"submission_ids": ids}
    resp = requests.post(url, json=data, headers=headers)
    print(f"🗑️  BULK DELETE {env} - {url} -> {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

def main():
    parser = argparse.ArgumentParser(description="List and delete 2290 submissions (admin only)")
    parser.add_argument('--list', action='store_true', help='List all submissions')
    parser.add_argument('--env', choices=['local', 'prod'], help='Override environment (local/prod)')
    args = parser.parse_args()

    # Override API_BASE if environment specified
    global API_BASE
    if args.env == 'local':
        API_BASE = "http://localhost:5000"
    elif args.env == 'prod':
        API_BASE = "https://send2290-app.onrender.com"

    # Always list submissions first
    all_ids = list_submissions()
    print(f"\nEnter a submission ID to delete, or type 'all' to delete all submissions:")
    user_input = input('> ').strip()
    if user_input.lower() == 'all':
        env = get_environment()
        confirm = input(f"⚠️  Are you sure you want to delete ALL ({len(all_ids)}) submissions from {env}? (yes/no): ").strip().lower()
        if confirm == 'yes':
            bulk_delete(all_ids)
        else:
            print("Aborted.")
            sys.exit(0)
    else:
        try:
            sub_id = int(user_input)
            if sub_id not in all_ids:
                print(f"Submission ID {sub_id} not found.")
                sys.exit(1)
            delete_single(sub_id)
        except ValueError:
            print("Invalid input. Please enter a valid submission ID or 'all'.")
            sys.exit(1)

if __name__ == "__main__":
    main()
