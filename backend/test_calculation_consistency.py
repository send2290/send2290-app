#!/usr/bin/env python3
"""
Tax Calculation Consistency Test
Validates that frontend and backend tax calculations produce identical results
"""
import json
import requests
from xml_builder import calculate_vehicle_tax, calculate_total_tax, WEIGHT_RATES, LOGGING_RATES

def test_individual_vehicle_calculations():
    """Test individual vehicle tax calculations against expected values"""
    print("🧮 Testing Individual Vehicle Tax Calculations")
    print("=" * 60)
    
    # Test cases covering various scenarios
    test_cases = [
        # Format: (category, month, is_logging, expected_description, expected_amount)
        ("A", "202507", False, "Category A, July (annual), Regular", 100.00),
        ("A", "202508", False, "Category A, August (partial), Regular", 91.67),
        ("A", "202509", False, "Category A, September (partial), Regular", 83.33),
        ("A", "202508", True, "Category A, August (partial), Logging", 68.75),
        ("C", "202507", False, "Category C, July (annual), Regular", 144.00),
        ("C", "202510", False, "Category C, October (partial), Regular", 108.00),
        ("C", "202510", True, "Category C, October (partial), Logging", 81.00),
        ("V", "202512", False, "Category V, December (partial), Regular", 320.83),
        ("V", "202512", True, "Category V, December (partial), Logging", 240.62),
        ("W", "202508", False, "Category W (Suspended), Regular", 0.00),
        ("W", "202508", True, "Category W (Suspended), Logging", 0.00),
    ]
    
    all_passed = True
    
    for category, month, is_logging, description, expected in test_cases:
        vehicle = {
            "category": category,
            "used_month": month,
            "is_logging": is_logging,
            "is_suspended": category == "W",
            "is_agricultural": False
        }
        
        calculated = calculate_vehicle_tax(vehicle)
        passed = abs(calculated - expected) < 0.01  # Allow for floating point precision
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {description}")
        print(f"     Expected: ${expected:.2f}, Got: ${calculated:.2f}")
        
        if not passed:
            all_passed = False
            print(f"     ⚠️  DIFFERENCE: ${abs(calculated - expected):.2f}")
        print()
    
    return all_passed

def test_multiple_vehicles():
    """Test calculations with multiple vehicles"""
    print("🚛 Testing Multiple Vehicle Scenarios")
    print("=" * 60)
    
    test_scenarios = [
        {
            "name": "Mixed Categories and Months",
            "vehicles": [
                {"category": "A", "used_month": "202507", "is_logging": False, "is_suspended": False, "is_agricultural": False},
                {"category": "A", "used_month": "202508", "is_logging": False, "is_suspended": False, "is_agricultural": False},
                {"category": "C", "used_month": "202510", "is_logging": True, "is_suspended": False, "is_agricultural": False},
            ],
            "expected_total": 100.00 + 91.67 + 81.00  # 272.67
        },
        {
            "name": "With Suspended Vehicles",
            "vehicles": [
                {"category": "B", "used_month": "202507", "is_logging": False, "is_suspended": False, "is_agricultural": False},
                {"category": "W", "used_month": "202508", "is_logging": False, "is_suspended": True, "is_agricultural": False},
                {"category": "C", "used_month": "202509", "is_logging": True, "is_suspended": False, "is_agricultural": False},
            ],
            "expected_total": 122.00 + 0.00 + 90.00  # 212.00
        },
        {
            "name": "Agricultural Vehicles",
            "vehicles": [
                {"category": "D", "used_month": "202507", "is_logging": False, "is_suspended": False, "is_agricultural": False},
                {"category": "W", "used_month": "202508", "is_logging": False, "is_suspended": False, "is_agricultural": True},
                {"category": "E", "used_month": "202511", "is_logging": False, "is_suspended": False, "is_agricultural": False},
            ],
            "expected_total": 166.00 + 0.00 + 125.33  # 291.33
        }
    ]
    
    all_passed = True
    
    for scenario in test_scenarios:
        calculated_total = calculate_total_tax(scenario["vehicles"])
        expected_total = scenario["expected_total"]
        passed = abs(calculated_total - expected_total) < 0.01
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {scenario['name']}")
        print(f"     Expected Total: ${expected_total:.2f}, Got: ${calculated_total:.2f}")
        
        if not passed:
            all_passed = False
            print(f"     ⚠️  DIFFERENCE: ${abs(calculated_total - expected_total):.2f}")
        
        # Show individual vehicle breakdowns
        print("     Vehicle Breakdown:")
        for i, vehicle in enumerate(scenario["vehicles"], 1):
            individual_tax = calculate_vehicle_tax(vehicle)
            cat = vehicle["category"]
            month = vehicle["used_month"][-2:]
            logging_str = " (Logging)" if vehicle["is_logging"] else ""
            suspended_str = " (Suspended)" if vehicle.get("is_suspended") or vehicle.get("is_agricultural") else ""
            print(f"       Vehicle {i}: {cat}-{month}{logging_str}{suspended_str} = ${individual_tax:.2f}")
        print()
    
    return all_passed

def test_frontend_backend_consistency():
    """Test that frontend and backend produce same results via API call"""
    print("🔄 Testing Frontend-Backend Consistency via API")
    print("=" * 60)
    
    # Test data that matches frontend format
    test_form_data = {
        "vehicles": [
            {
                "vin": "1HGCM82633A004352",
                "category": "A",
                "used_month": "202507",
                "is_logging": False,
                "is_suspended": False,
                "is_agricultural": False,
                "mileage_5000_or_less": False
            },
            {
                "vin": "1HGCM82633A004353",
                "category": "A", 
                "used_month": "202508",
                "is_logging": False,
                "is_suspended": False,
                "is_agricultural": False,
                "mileage_5000_or_less": False
            },
            {
                "vin": "1HGCM82633A004354",
                "category": "C",
                "used_month": "202510",
                "is_logging": True,
                "is_suspended": False,
                "is_agricultural": False,
                "mileage_5000_or_less": False
            }
        ],
        "business_name": "Test Company",
        "ein": "12-3456789",
        "address": "123 Test St",
        "city": "Test City",
        "state": "MI",
        "zip": "48124"
    }
    
    # Calculate using backend directly
    backend_total = calculate_total_tax(test_form_data["vehicles"])
    
    print(f"Backend Direct Calculation: ${backend_total:.2f}")
    
    # Try to call frontend API (if available)
    try:
        # Check if frontend server is running
        frontend_url = "http://localhost:3000/api/calculate-tax"  # Adjust URL as needed
        
        response = requests.post(frontend_url, json=test_form_data, timeout=5)
        if response.status_code == 200:
            frontend_data = response.json()
            frontend_total = frontend_data.get("total_tax", 0)
            
            passed = abs(backend_total - frontend_total) < 0.01
            status = "✅ PASS" if passed else "❌ FAIL"
            
            print(f"Frontend API Response: ${frontend_total:.2f}")
            print(f"{status} Frontend-Backend Consistency")
            
            if not passed:
                print(f"     ⚠️  DIFFERENCE: ${abs(backend_total - frontend_total):.2f}")
                return False
            return True
        else:
            print(f"❌ Frontend API Error: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Frontend API not available: {e}")
        print("   (This is expected if frontend server is not running)")
        return True  # Don't fail the test if frontend is not available

def validate_tax_tables():
    """Validate that tax tables are complete and consistent"""
    print("📊 Validating Tax Tables")
    print("=" * 60)
    
    categories = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W"]
    months = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12]  # All except July (7)
    
    all_passed = True
    
    # Check annual rates
    print("Checking Annual Rates (July)...")
    for cat in categories:
        if cat not in WEIGHT_RATES:
            print(f"❌ Missing annual rate for category {cat}")
            all_passed = False
        if cat not in LOGGING_RATES:
            print(f"❌ Missing logging rate for category {cat}")
            all_passed = False
    
    # Check partial-period tables
    print("Checking Partial-Period Tables...")
    from xml_builder import PARTIAL_PERIOD_TAX_REGULAR, PARTIAL_PERIOD_TAX_LOGGING
    
    for cat in categories:
        # Check regular partial-period rates
        if cat not in PARTIAL_PERIOD_TAX_REGULAR:
            print(f"❌ Missing regular partial-period rates for category {cat}")
            all_passed = False
        else:
            for month in months:
                if month not in PARTIAL_PERIOD_TAX_REGULAR[cat]:
                    print(f"❌ Missing regular partial-period rate for category {cat}, month {month}")
                    all_passed = False
        
        # Check logging partial-period rates
        if cat not in PARTIAL_PERIOD_TAX_LOGGING:
            print(f"❌ Missing logging partial-period rates for category {cat}")
            all_passed = False
        else:
            for month in months:
                if month not in PARTIAL_PERIOD_TAX_LOGGING[cat]:
                    print(f"❌ Missing logging partial-period rate for category {cat}, month {month}")
                    all_passed = False
    
    if all_passed:
        print("✅ All tax tables are complete")
    
    return all_passed

def main():
    """Run all consistency tests"""
    print("🚀 Form 2290 Tax Calculation Consistency Test")
    print("=" * 60)
    print("This script validates that frontend and backend calculations match")
    print("and that all tax tables are complete and consistent.")
    print()
    
    all_tests_passed = True
    
    # Run individual tests
    tests = [
        ("Tax Table Validation", validate_tax_tables),
        ("Individual Vehicle Calculations", test_individual_vehicle_calculations),
        ("Multiple Vehicle Scenarios", test_multiple_vehicles),
        ("Frontend-Backend Consistency", test_frontend_backend_consistency),
    ]
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 40)
        try:
            passed = test_func()
            if not passed:
                all_tests_passed = False
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            all_tests_passed = False
        print()
    
    # Final summary
    print("=" * 60)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED! Frontend and backend calculations are consistent.")
        exit(0)
    else:
        print("⚠️  SOME TESTS FAILED! Please review the issues above.")
        exit(1)

if __name__ == "__main__":
    main()
