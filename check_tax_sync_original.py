#!/usr/bin/env python3
"""
Automated Tax Calculatio    if regular_match and logging_match:
        safe_print(safe_format_status("success", "Backend annual rates match shared tables"))
        return True
    else:
        safe_print(safe_format_status("error", "Backend annual rates don't match shared tables"))
        return False

def check_frontend_tables():
    """Check if frontend tables exist and have required exports"""
    safe_print(safe_format_status("info", "Checking Frontend Tax Tables..."))cker

This script can be run as part of CI/CD to ensure frontend and backend
tax calculations remain synchronized.
"""

import json
import sys
from pathlib import Path
from safe_print import safe_print, safe_format_status

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
        print("  ✅ Backend annual rates match shared tables")
        return True
    else:
        print("  ❌ Backend annual rates don't match shared tables")
        return False

def check_frontend_tables():
    """Check if frontend tables exist and are accessible"""
    print("🌐 Checking Frontend Tax Tables...")
    
    frontend_constants = Path("frontend/app/constants/formData.ts")
    if not frontend_constants.exists():
        print("  ❌ Frontend constants file not found")
        return False
    
    # Read the frontend file to check for tax table exports
    content = frontend_constants.read_text()
    
    required_exports = [
        "export const weightCategories",
        "export const loggingRates", 
        "export const partialPeriodTaxRegular",
        "export const partialPeriodTaxLogging"
    ]
    
    missing_exports = []
    for export in required_exports:
        if export not in content:
            missing_exports.append(export)
    
    if missing_exports:
        print(f"  ❌ Missing frontend exports: {missing_exports}")
        return False
    else:
        print("  ✅ Frontend tax tables found")
        return True

def run_calculation_tests():
    """Run the full calculation validation"""
    print("🧪 Running Calculation Tests...")
    
    import subprocess
    result = subprocess.run([
        sys.executable, "validate_calculations.py"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("  ✅ All calculation tests passed")
        return True
    else:
        print("  ❌ Calculation tests failed")
        print(result.stdout)
        print(result.stderr)
        return False

def main():
    """Main sync checking function"""
    print("🔄 Tax Calculation Sync Check")
    print("=" * 40)
    
    checks = [
        ("Backend Tables", check_backend_tables),
        ("Frontend Tables", check_frontend_tables), 
        ("Calculation Tests", run_calculation_tests)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"  ❌ {check_name} failed with error: {e}")
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✅ ALL SYNC CHECKS PASSED")
        print("Frontend and backend calculations are synchronized!")
    else:
        print("❌ SYNC CHECKS FAILED")
        print("Frontend and backend calculations may be out of sync!")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
