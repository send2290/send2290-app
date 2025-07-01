#!/usr/bin/env python3
"""
Production Log Analysis and Monitoring Tools
Utilities for analyzing and monitoring production audit logs
"""

import os
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

class ProductionLogAnalyzer:
    def __init__(self, log_file_path='Audit/productionaudit.log'):
        self.log_file_path = log_file_path
        
    def analyze_logs(self, hours_back=24):
        """Analyze production logs for the specified time period"""
        
        if not os.path.exists(self.log_file_path):
            print(f"❌ Production log file not found: {self.log_file_path}")
            return
            
        print(f"🔍 Analyzing Production Logs (Last {hours_back} hours)")
        print("=" * 60)
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Counters for different types of events
        login_attempts = {'success': 0, 'failed': 0}
        form_submissions = 0
        document_downloads = 0
        admin_actions = 0
        security_events = 0
        api_calls = Counter()
        error_events = Counter()
        users = set()
        slow_requests = []
        failed_logins = []
        
        with open(self.log_file_path, 'r') as f:
            for line in f:
                try:
                    # Parse timestamp
                    timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not timestamp_match:
                        continue
                        
                    log_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                    if log_time < cutoff_time:
                        continue
                    
                    # Extract user email
                    user_match = re.search(r'USER: ([^\s|]+)', line)
                    if user_match:
                        users.add(user_match.group(1))
                    
                    # Analyze different log types
                    if 'LOGIN_ATTEMPT: SUCCESS' in line:
                        login_attempts['success'] += 1
                    elif 'LOGIN_ATTEMPT: FAILED' in line:
                        login_attempts['failed'] += 1
                        failed_logins.append(line.strip())
                    elif 'FORM_SUBMISSION:' in line:
                        form_submissions += 1
                    elif 'DOCUMENT_ACCESS: DOWNLOAD' in line:
                        document_downloads += 1
                    elif 'ADMIN_ACTION:' in line:
                        admin_actions += 1
                    elif 'SECURITY_EVENT:' in line:
                        security_events += 1
                    elif 'API_USAGE:' in line:
                        # Extract endpoint
                        endpoint_match = re.search(r'(GET|POST|PUT|DELETE) ([^\s|]+)', line)
                        if endpoint_match:
                            method_endpoint = f"{endpoint_match.group(1)} {endpoint_match.group(2)}"
                            api_calls[method_endpoint] += 1
                        
                        # Check for slow requests (>2000ms)
                        time_match = re.search(r'TIME: (\d+)ms', line)
                        if time_match and int(time_match.group(1)) > 2000:
                            slow_requests.append(line.strip())
                    elif 'ERROR_EVENT:' in line:
                        error_match = re.search(r'ERROR_EVENT: ([^\s|]+)', line)
                        if error_match:
                            error_events[error_match.group(1)] += 1
                            
                except Exception as e:
                    continue
        
        # Display analysis results
        print(f"\n📊 SUMMARY STATISTICS (Last {hours_back} hours)")
        print("-" * 40)
        print(f"👥 Active Users: {len(users)}")
        print(f"✅ Successful Logins: {login_attempts['success']}")
        print(f"❌ Failed Logins: {login_attempts['failed']}")
        print(f"📝 Form Submissions: {form_submissions}")
        print(f"📥 Document Downloads: {document_downloads}")
        print(f"👑 Admin Actions: {admin_actions}")
        print(f"🔒 Security Events: {security_events}")
        print(f"🐌 Slow Requests (>2s): {len(slow_requests)}")
        
        # Top API endpoints
        if api_calls:
            print(f"\n🔥 TOP API ENDPOINTS")
            print("-" * 25)
            for endpoint, count in api_calls.most_common(10):
                print(f"  {endpoint}: {count} calls")
        
        # Error breakdown
        if error_events:
            print(f"\n🚨 ERROR BREAKDOWN")
            print("-" * 20)
            for error_type, count in error_events.most_common():
                print(f"  {error_type}: {count} occurrences")
        
        # Security alerts
        if failed_logins:
            print(f"\n🔐 FAILED LOGIN ATTEMPTS")
            print("-" * 25)
            for login in failed_logins[-5:]:  # Show last 5
                print(f"  {login}")
        
        if slow_requests:
            print(f"\n⏱️  SLOW REQUESTS (>2 seconds)")
            print("-" * 30)
            for request in slow_requests[-5:]:  # Show last 5
                print(f"  {request}")
        
        # Active users list
        if users:
            print(f"\n👤 ACTIVE USERS")
            print("-" * 15)
            for user in sorted(users):
                print(f"  {user}")
    
    def monitor_security_events(self):
        """Monitor for critical security events"""
        
        print("🔒 Security Event Monitor")
        print("=" * 30)
        
        if not os.path.exists(self.log_file_path):
            print(f"❌ Log file not found: {self.log_file_path}")
            return
        
        security_patterns = {
            'BRUTE_FORCE': r'SECURITY_EVENT: BRUTE_FORCE',
            'UNAUTHORIZED_ACCESS': r'SECURITY_EVENT: UNAUTHORIZED',
            'DDOS': r'SECURITY_EVENT: DDOS',
            'SUSPICIOUS_ACTIVITY': r'SECURITY_EVENT: SUSPICIOUS',
            'MULTIPLE_FAILED_LOGINS': r'LOGIN_ATTEMPT: FAILED'
        }
        
        recent_events = defaultdict(list)
        
        # Check last 1000 lines for recent events
        with open(self.log_file_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines[-1000:]:  # Last 1000 entries
            for event_type, pattern in security_patterns.items():
                if re.search(pattern, line):
                    recent_events[event_type].append(line.strip())
        
        if not recent_events:
            print("✅ No critical security events detected")
            return
        
        for event_type, events in recent_events.items():
            if events:
                print(f"\n⚠️  {event_type}: {len(events)} event(s)")
                for event in events[-3:]:  # Show last 3 of each type
                    print(f"    {event}")
    
    def generate_daily_report(self):
        """Generate a daily production report"""
        
        print("📋 Daily Production Report")
        print("=" * 30)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Analyze last 24 hours
        self.analyze_logs(hours_back=24)
        
        print("\n" + "=" * 60)
        self.monitor_security_events()

def main():
    """Main function to run log analysis"""
    
    analyzer = ProductionLogAnalyzer()
    
    print("🚀 Production Log Analysis Tool")
    print("Choose an option:")
    print("1. Generate Daily Report")
    print("2. Analyze Last 24 Hours")
    print("3. Monitor Security Events")
    print("4. Analyze Custom Time Period")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            analyzer.generate_daily_report()
        elif choice == '2':
            analyzer.analyze_logs(hours_back=24)
        elif choice == '3':
            analyzer.monitor_security_events()
        elif choice == '4':
            hours = int(input("Enter hours to analyze: "))
            analyzer.analyze_logs(hours_back=hours)
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
