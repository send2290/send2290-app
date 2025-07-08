#!/usr/bin/env python3
"""
Tax Calculation Mismatch Notifier

This script runs the validation and sends notifications when mismatches are found.
Configure your notification preferences below.
"""

import subprocess
import json
import sys
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_env_vars():
    """Load environment variables from .env file"""
    env_vars = {}
    env_paths = [
        ".env",
        "backend/.env",
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "backend", ".env")
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
                break
            except Exception as e:
                print(f"Warning: Could not read {env_path}: {e}")
    
    return env_vars

# Load environment variables
ENV_VARS = load_env_vars()
ADMIN_EMAIL = ENV_VARS.get('ADMIN_EMAIL', 'admin@example.com')

# Configuration
NOTIFICATION_CONFIG = {
    "email": {
        "enabled": True,  # Email notifications enabled
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": ADMIN_EMAIL,  # Uses ADMIN_EMAIL from .env
        "sender_password": "your-app-password",  # Replace with your Gmail app password
        "recipients": [ADMIN_EMAIL]  # Uses ADMIN_EMAIL from .env
    },
    "webhook": {
        "enabled": False,  # Set to True to enable webhook notifications
        "slack_webhook": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        "discord_webhook": "https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK"
    },
    "file_log": {
        "enabled": True,  # Set to False to disable file logging
        "log_file": "tax_sync_alerts.log"
    }
}

def log_to_file(message):
    """Log message to file with timestamp"""
    if not NOTIFICATION_CONFIG["file_log"]["enabled"]:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = NOTIFICATION_CONFIG["file_log"]["log_file"]
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def send_email_notification(report_data):
    """Send email notification about mismatches"""
    if not NOTIFICATION_CONFIG["email"]["enabled"]:
        return
        
    config = NOTIFICATION_CONFIG["email"]
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config["sender_email"]
        msg['To'] = ", ".join(config["recipients"])
        msg['Subject'] = "🚨 Form 2290 Tax Calculation Mismatch Alert"
        
        if report_data["all_match"]:
            body = "✅ All tax calculations are synchronized and working correctly."
        else:
            body = f"""
🚨 TAX CALCULATION MISMATCH DETECTED

Summary:
- Total Tests: {report_data["total_tests"]}
- Successful Matches: {report_data["matches"]}
- Mismatches Found: {report_data["mismatches"]}

Failed Test Cases:
"""
            for mismatch in report_data["mismatches"]:
                backend_tax = mismatch.get("backend_tax", "N/A")
                frontend_tax = mismatch.get("frontend_tax", "N/A")
                body += f"• {mismatch['test_case']}: Backend=${backend_tax}, Frontend=${frontend_tax}\n"
            
            body += f"""
This indicates that the frontend and backend tax calculations are out of sync.
Please review the code changes and update the tax tables accordingly.

Report generated: {report_data.get("timestamp", datetime.now().isoformat())}
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        text = msg.as_string()
        server.sendmail(config["sender_email"], config["recipients"], text)
        server.quit()
        
        print(f"📧 Email notification sent to: {', '.join(config['recipients'])}")
        log_to_file(f"Email notification sent to {len(config['recipients'])} recipients")
        
    except Exception as e:
        print(f"❌ Failed to send email notification: {e}")
        log_to_file(f"Failed to send email notification: {e}")

def send_webhook_notification(report_data):
    """Send webhook notifications (Slack/Discord)"""
    if not NOTIFICATION_CONFIG["webhook"]["enabled"]:
        return
        
    try:
        import requests
    except ImportError:
        print("❌ 'requests' library not installed. Install with: pip install requests")
        return
    
    config = NOTIFICATION_CONFIG["webhook"]
    
    if report_data["all_match"]:
        message = "✅ Form 2290 tax calculations are synchronized"
        color = "good"
    else:
        message = f"🚨 {report_data['mismatches']} tax calculation mismatches found in Form 2290"
        color = "danger"
    
    # Slack notification
    if config.get("slack_webhook"):
        slack_payload = {
            "text": message,
            "attachments": [{
                "color": color,
                "title": "Tax Calculation Sync Check",
                "fields": [
                    {"title": "Total Tests", "value": str(report_data["total_tests"]), "short": True},
                    {"title": "Matches", "value": str(report_data["matches"]), "short": True},
                    {"title": "Mismatches", "value": str(report_data["mismatches"]), "short": True}
                ]
            }]
        }
        
        try:
            response = requests.post(config["slack_webhook"], json=slack_payload)
            if response.status_code == 200:
                print("📱 Slack notification sent")
                log_to_file("Slack notification sent successfully")
            else:
                print(f"❌ Slack notification failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Slack notification error: {e}")
    
    # Discord notification
    if config.get("discord_webhook"):
        discord_payload = {
            "content": message,
            "embeds": [{
                "title": "Tax Calculation Sync Check",
                "color": 0x00ff00 if report_data["all_match"] else 0xff0000,
                "fields": [
                    {"name": "Total Tests", "value": str(report_data["total_tests"]), "inline": True},
                    {"name": "Matches", "value": str(report_data["matches"]), "inline": True},
                    {"name": "Mismatches", "value": str(report_data["mismatches"]), "inline": True}
                ]
            }]
        }
        
        try:
            response = requests.post(config["discord_webhook"], json=discord_payload)
            if response.status_code == 204:
                print("📱 Discord notification sent")
                log_to_file("Discord notification sent successfully")
            else:
                print(f"❌ Discord notification failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord notification error: {e}")

def run_validation_and_notify():
    """Run validation script and send notifications if needed"""
    print("🔍 Running tax calculation validation...")
    
    try:
        # Run the validation script
        result = subprocess.run([sys.executable, "validate_calculations.py"], 
                              capture_output=True, text=True, timeout=120)
        
        # Load the report
        report_file = "tax_validation_report.json"
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                report_data = json.load(f)
        else:
            print("❌ Validation report not found")
            log_to_file("Validation report file not found")
            return 1
        
        # Check results
        if report_data["all_match"]:
            print("✅ All tax calculations match - no action needed")
            log_to_file("All tax calculations match - validation passed")
            
            # Optionally send success notifications (uncomment if desired)
            # send_email_notification(report_data)
            # send_webhook_notification(report_data)
            
            return 0
        else:
            print(f"🚨 {report_data['mismatches']} mismatches found - sending notifications...")
            log_to_file(f"Tax calculation mismatches detected: {report_data['mismatches']} failures")
            
            # Send all configured notifications
            send_email_notification(report_data)
            send_webhook_notification(report_data)
            
            return 1
            
    except subprocess.TimeoutExpired:
        error_msg = "Validation script timed out"
        print(f"❌ {error_msg}")
        log_to_file(error_msg)
        return 1
    except Exception as e:
        error_msg = f"Error running validation: {e}"
        print(f"❌ {error_msg}")
        log_to_file(error_msg)
        return 1

def main():
    """Main function"""
    print("📊 Form 2290 Tax Calculation Monitor")
    print("=" * 40)
    
    # Show loaded configuration
    print(f"\n📧 Email Configuration:")
    print(f"  Admin Email: {ADMIN_EMAIL}")
    print(f"  Email Notifications: {'✅ Enabled' if NOTIFICATION_CONFIG['email']['enabled'] else '❌ Disabled'}")
    
    # Show notification configuration status
    print("\n🔧 Notification Configuration:")
    print(f"  📧 Email: {'✅ Enabled' if NOTIFICATION_CONFIG['email']['enabled'] else '❌ Disabled'}")
    print(f"  📱 Webhook: {'✅ Enabled' if NOTIFICATION_CONFIG['webhook']['enabled'] else '❌ Disabled'}")
    print(f"  📄 File Log: {'✅ Enabled' if NOTIFICATION_CONFIG['file_log']['enabled'] else '❌ Disabled'}")
    print()
    
    exit_code = run_validation_and_notify()
    
    print("\n" + "=" * 40)
    if exit_code == 0:
        print("✅ Monitoring completed successfully")
    else:
        print("❌ Issues detected - check notifications")
    
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
