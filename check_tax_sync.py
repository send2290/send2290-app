#!/usr/bin/env python3
"""
Automated Tax Calculation Sync Checker

This script can be run as part of CI/CD to ensure frontend and backend
tax calculations remain synchronized.
"""

import json
import sys
import subprocess
from pathlib import Path

def safe_print(text):
    """Print text with fallback for Unicode issues on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = ''.join(char for char in text if ord(char) < 128)
        print(safe_text)

def safe_format_status(status, text):
    """Format status messages with safe Unicode handling"""
    try:
        if status == "success":
            return f"✅ {text}"
        elif status == "error":
            return f"❌ {text}"
        elif status == "info":
            return f"🔍 {text}"
        else:
            return text
    except UnicodeEncodeError:
        if status == "success":
            return f"[OK] {text}"
        elif status == "error":
            return f"[ERROR] {text}"
        elif status == "info":
            return f"[INFO] {text}"
        else:
            return text

def load_shared_tax_tables():
    """Load the shared tax tables JSON"""
    try:
        with open("shared/tax_tables.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        safe_print(safe_format_status("error", "Shared tax tables not found at shared/tax_tables.json"))
        return None

def check_backend_tables():
    """Check if backend tables match shared tables"""
    safe_print(safe_format_status("info", "Checking Backend Tax Tables..."))
    
    sys.path.append("backend")
    try:
        from xml_builder import WEIGHT_RATES, LOGGING_RATES, PARTIAL_PERIOD_TAX_REGULAR, PARTIAL_PERIOD_TAX_LOGGING
    except ImportError as e:
        safe_print(safe_format_status("error", f"Failed to import backend tables: {e}"))
        return False
    
    shared_tables = load_shared_tax_tables()
    if not shared_tables:
        return False
    
    # Check annual rates
    backend_regular = WEIGHT_RATES
    backend_logging = LOGGING_RATES
    shared_regular = shared_tables["annual_rates"]["regular"]
    shared_logging = shared_tables["annual_rates"]["logging"]
    
    regular_match = all(
        abs(backend_regular.get(cat, 0) - shared_regular.get(cat, 0)) < 0.01
        for cat in set(list(backend_regular.keys()) + list(shared_regular.keys()))
    )
    
    logging_match = all(
        abs(backend_logging.get(cat, 0) - shared_logging.get(cat, 0)) < 0.01
        for cat in set(list(backend_logging.keys()) + list(shared_logging.keys()))
    )
    
    if regular_match and logging_match:
        safe_print(safe_format_status("success", "Backend annual rates match shared tables"))
        return True
    else:
        safe_print(safe_format_status("error", "Backend annual rates don't match shared tables"))
        return False

def check_frontend_tables():
    """Check if frontend tables exist and have required exports"""
    safe_print(safe_format_status("info", "Checking Frontend Tax Tables..."))
    
    frontend_file = Path("frontend/app/constants/formData.ts")
    if not frontend_file.exists():
        safe_print(safe_format_status("error", "Frontend constants file not found"))
        return False
    
    # Read frontend file and check for tax table exports
    try:
        with open(frontend_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        required_exports = [
            "weightCategories",
            "loggingRates", 
            "partialPeriodTaxRegular",
            "partialPeriodTaxLogging"
        ]
        
        missing_exports = [exp for exp in required_exports if exp not in content]
        
        if missing_exports:
            safe_print(safe_format_status("error", f"Missing frontend exports: {missing_exports}"))
            return False
        else:
            safe_print(safe_format_status("success", "Frontend tax tables found"))
            return True
            
    except Exception as e:
        safe_print(safe_format_status("error", f"Error reading frontend file: {e}"))
        return False

def run_calculation_tests():
    """Run the validation script to test calculations"""
    safe_print(safe_format_status("info", "Running Calculation Tests..."))
    
    try:
        result = subprocess.run([sys.executable, "validate_calculations.py"], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            safe_print(safe_format_status("success", "All calculation tests passed"))
            return True
        else:
            safe_print(safe_format_status("error", "Calculation tests failed"))
            print(result.stdout)
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        safe_print(safe_format_status("error", "Calculation tests timed out"))
        return False
    except Exception as e:
        safe_print(safe_format_status("error", f"Error running calculation tests: {e}"))
        return False

def main():
    """Main sync check function"""
    safe_print("Tax Calculation Sync Check")
    print("=" * 40)
    
    checks = [
        ("Backend Tax Tables", check_backend_tables),
        ("Frontend Tax Tables", check_frontend_tables),
        ("Calculation Tests", run_calculation_tests)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
        except Exception as e:
            safe_print(safe_format_status("error", f"{check_name} failed with error: {e}"))
            all_passed = False
    
    print("=" * 40)
    if all_passed:
        safe_print(safe_format_status("success", "ALL SYNC CHECKS PASSED"))
        return 0
    else:
        safe_print(safe_format_status("error", "SYNC CHECKS FAILED"))
        safe_print("Frontend and backend calculations may be out of sync!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
