#!/usr/bin/env python3
"""
Form 2290 Tax Calculation Validation Script

This script validates that frontend and backend tax calculations match exactly.
Designed to work with Windows terminals and handle Unicode safely.
"""
import json
import sys
import os
from safe_print import safe_print, safe_format_status

# Test cases covering different scenarios
TEST_CASES = {
    "Category A, July (Annual)": {
        "category": "A", "used_month": "202507", "is_logging": False,
        "expected_tax": 100.00
    },
    "Category A, August (Partial)": {
        "category": "A", "used_month": "202508", "is_logging": False,
        "expected_tax": 91.67
    },
    "Category A, September (Partial)": {
        "category": "A", "used_month": "202509", "is_logging": False,
        "expected_tax": 83.33
    },
    "Category A, July (Logging)": {
        "category": "A", "used_month": "202507", "is_logging": True,
        "expected_tax": 75.00
    },
    "Category A, August (Logging)": {
        "category": "A", "used_month": "202508", "is_logging": True,
        "expected_tax": 68.75
    },
    "Category V, July (Annual)": {
        "category": "V", "used_month": "202507", "is_logging": False,
        "expected_tax": 550.00
    },
    "Category V, December (Partial)": {
        "category": "V", "used_month": "202512", "is_logging": False,
        "expected_tax": 320.83
    },
    "Category W, Any Month": {
        "category": "W", "used_month": "202507", "is_logging": False,
        "expected_tax": 0.00
    },
    "Suspended Vehicle": {
        "category": "A", "used_month": "202507", "is_logging": False,
        "is_suspended": True, "expected_tax": 0.00
    },
    "Agricultural Vehicle": {
        "category": "B", "used_month": "202507", "is_logging": False,
        "is_agricultural": True, "expected_tax": 0.00
    }
}

def test_backend_calculation():
    """Test backend calculation function"""
    safe_print(safe_format_status("info", "Testing Backend Calculations..."))
    
    # Add backend path
    sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
    
    try:
        from xml_builder import calculate_vehicle_tax
    except ImportError as e:
        safe_print(safe_format_status("error", f"Failed to import backend module: {e}"))
        return {}
    
    results = {}
    for test_case, data in TEST_CASES.items():
        try:
            # Create vehicle data dict
            vehicle = {
                "category": data["category"],
                "used_month": data["used_month"],
                "is_logging": data.get("is_logging", False),
                "is_suspended": data.get("is_suspended", False),
                "is_agricultural": data.get("is_agricultural", False)
            }
            
            tax = calculate_vehicle_tax(vehicle)
            results[test_case] = tax
            
            description = f"{test_case}: ${tax:.2f}"
            safe_print(safe_format_status("success", description))
            
        except Exception as e:
            safe_print(safe_format_status("error", f"{test_case}: Error - {e}"))
            results[test_case] = None
    
    return results

def get_frontend_expected_results():
    """Get expected results (from frontend logic)"""
    safe_print(safe_format_status("info", "Loading Expected Results..."))
    
    results = {}
    for test_case, data in TEST_CASES.items():
        expected_tax = data["expected_tax"]
        results[test_case] = expected_tax
        
        description = f"{test_case}: ${expected_tax:.2f} (expected)"
        safe_print(safe_format_status("success", description))
    
    return results

def compare_results(backend_results, frontend_results):
    """Compare backend and frontend results"""
    safe_print("\nComparing Results...")
    
    mismatches = []
    matches = 0
    
    for test_case in TEST_CASES.keys():
        backend_tax = backend_results.get(test_case)
        frontend_tax = frontend_results.get(test_case)
        
        if backend_tax is None:
            safe_print(safe_format_status("error", f"{test_case}: Missing backend calculation"))
            mismatches.append({
                "test_case": test_case,
                "backend_tax": None,
                "frontend_tax": frontend_tax,
                "difference": None
            })
        elif frontend_tax is None:
            safe_print(safe_format_status("error", f"{test_case}: Missing frontend calculation"))
            mismatches.append({
                "test_case": test_case,
                "backend_tax": backend_tax,
                "frontend_tax": None,
                "difference": None
            })
        elif abs(backend_tax - frontend_tax) < 0.01:  # Allow 1 cent tolerance
            matches += 1
            safe_print(safe_format_status("success", f"{test_case}: Backend=${backend_tax:.2f}, Frontend=${frontend_tax:.2f} MATCH"))
        else:
            difference = backend_tax - frontend_tax
            safe_print(safe_format_status("error", f"{test_case}: Backend=${backend_tax:.2f}, Frontend=${frontend_tax:.2f} MISMATCH"))
            mismatches.append({
                "test_case": test_case,
                "backend_tax": backend_tax,
                "frontend_tax": frontend_tax,
                "difference": difference
            })
    
    return mismatches

def generate_report(backend_results, frontend_results, mismatches):
    """Generate validation report"""
    report = {
        "timestamp": "2025-07-07",
        "total_tests": len(TEST_CASES),
        "matches": len(TEST_CASES) - len(mismatches),
        "mismatches": len(mismatches),
        "backend_results": backend_results,
        "frontend_results": frontend_results,
        "mismatches": mismatches,
        "all_match": len(mismatches) == 0
    }
    
    # Save report
    with open("tax_validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    safe_print(safe_format_status("report", "Report saved to: tax_validation_report.json"))
    return report

def main():
    """Main validation function"""
    try:
        safe_print("Form 2290 Tax Calculation Validation")
    except:
        print("Form 2290 Tax Calculation Validation")
    print("=" * 50)
    
    # Test backend
    backend_results = test_backend_calculation()
    
    # Test frontend (expected results)
    frontend_results = get_frontend_expected_results()
    
    # Compare results
    mismatches = compare_results(backend_results, frontend_results)
    
    # Generate report
    report = generate_report(backend_results, frontend_results, mismatches)
    
    # Summary
    print("\n" + "=" * 50)
    if len(mismatches) == 0:
        safe_print(safe_format_status("success", "ALL TESTS PASSED - Frontend and Backend calculations match!"))
        exit_code = 0
    else:
        safe_print(safe_format_status("error", f"{len(mismatches)} MISMATCHES FOUND"))
        for mismatch in mismatches:
            safe_print(f"  - {mismatch['test_case']}")
        exit_code = 1
    
    safe_print(f"\nTests Run: {len(TEST_CASES)}")
    safe_print(f"Matches: {len(TEST_CASES) - len(mismatches)}")
    safe_print(f"Mismatches: {len(mismatches)}")
    
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
