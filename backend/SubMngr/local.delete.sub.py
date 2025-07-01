import requests
import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(dotenv_path="../.env")

# Localhost configuration
API_BASE = "http://localhost:5000"

# Get local admin token from environment variable
LOCAL_ADMIN_TOKEN = os.getenv('LOCAL_ADMIN_TOKEN')
if not LOCAL_ADMIN_TOKEN:
    print("❌ Error: LOCAL_ADMIN_TOKEN not found in .env file")
    print("Please add LOCAL_ADMIN_TOKEN=your_local_token_here to your .env file")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {LOCAL_ADMIN_TOKEN}"
}

def get_environment():
    """Determine which environment we're targeting"""
    return "LOCAL"

def list_submissions():
    env = get_environment()
    print(f"\n🌍 Targeting: {env} Environment ({API_BASE})")
    
    url = f"{API_BASE}/admin/submissions"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {API_BASE}")
        print("Make sure your local Flask server is running on port 5000")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"❌ Timeout Error: Request to {API_BASE} timed out")
        sys.exit(1)
    
    if resp.status_code != 200:
        print(f"Failed to fetch submissions: {resp.status_code}")
        print(resp.text)
        sys.exit(1)
    
    submissions = resp.json()
    # Handle dict response with 'submissions' key
    if isinstance(submissions, dict) and 'submissions' in submissions:
        submissions = submissions['submissions']
    
    if not submissions:
        print("No submissions found in local database.")
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
    try:
        resp = requests.delete(url, headers=headers, timeout=10)
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {API_BASE}")
        return
    except requests.exceptions.Timeout:
        print(f"❌ Timeout Error: Request timed out")
        return
    
    print(f"🗑️  DELETE {env} - {url} -> {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

def bulk_delete(ids):
    env = get_environment()
    url = f"{API_BASE}/admin/bulk-delete"
    data = {"submission_ids": ids}
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=30)
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {API_BASE}")
        return
    except requests.exceptions.Timeout:
        print(f"❌ Timeout Error: Request timed out")
        return
    
    print(f"🗑️  BULK DELETE {env} - {url} -> {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

def main():
    parser = argparse.ArgumentParser(description="List and delete 2290 submissions from LOCAL environment (admin only)")
    parser.add_argument('--list', action='store_true', help='List all submissions')
    args = parser.parse_args()

    print("🏠 LOCAL DELETION SCRIPT - Targeting localhost:5000")
    print("=" * 50)

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
