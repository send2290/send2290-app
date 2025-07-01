import argparse
import os

def view_logs(log_type, lines=50):
    """View recent audit log entries"""
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
    parser.add_argument('log_type', choices=['local', 'production'], help='Which audit log to view')
    parser.add_argument('--lines', type=int, default=50, help='Number of recent lines to show (default: 50)')
    
    args = parser.parse_args()
    view_logs(args.log_type, args.lines)

if __name__ == "__main__":
    main()