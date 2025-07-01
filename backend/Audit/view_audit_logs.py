import argparse
import os
from datetime import datetime

def show_log_info():
    """Show information about available log files"""
    print("📊 Log File Information:")
    print("=" * 60)
    
    # Check files in current directory (Audit folder) - these are the active ones now
    log_files = [
        ('local', 'localaudit.log'),
        ('production', 'productionaudit.log')
    ]
    
    for log_type, filepath in log_files:
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
            
            with open(filepath, 'r') as f:
                line_count = sum(1 for _ in f)
            
            print(f"✅ {log_type}: {filepath}")
            print(f"   📅 Last modified: {modified}")
            print(f"   📏 Size: {size} bytes")
            print(f"   📄 Lines: {line_count}")
            print()
        else:
            print(f"❌ {log_type}: {filepath} (not found)")
    
    print("=" * 60)

def view_logs(log_type, lines=50):
    """View recent audit log entries"""
    # Since the log files are now in the Audit directory (current directory), look locally
    if log_type == 'local':
        filename = 'localaudit.log'
    elif log_type == 'production':
        filename = 'productionaudit.log'
    else:
        print("Invalid log type. Use 'local' or 'production'")
        return
    
    if not os.path.exists(filename):
        print(f"❌ Log file {filename} not found")
        return
    
    print(f"📋 Viewing last {lines} entries from {filename}:")
    print("=" * 80)
    
    try:
        with open(filename, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
            
        for line in recent_lines:
            print(line.rstrip())
            
        print("=" * 80)
        print(f"Total lines in log: {len(all_lines)}")
        print(f"Showing last: {len(recent_lines)}")
        
    except Exception as e:
        print(f"Error reading log file: {e}")

def main():
    parser = argparse.ArgumentParser(description="View audit logs")
    parser.add_argument('log_type', nargs='?', choices=['local', 'production', 'info'], 
                       help='Which audit log to view, or "info" to show log file information')
    parser.add_argument('--lines', type=int, default=50, help='Number of recent lines to show (default: 50)')
    
    args = parser.parse_args()
    
    if args.log_type == 'info' or args.log_type is None:
        show_log_info()
        if args.log_type is None:
            print("Usage: python view_audit_logs.py [local|production|info] [--lines N]")
    else:
        view_logs(args.log_type, args.lines)

if __name__ == "__main__":
    main()