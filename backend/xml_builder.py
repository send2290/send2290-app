"""
IRS-compliant Form 2290 XML builder based on 2025v1.0 schema
Enhanced with full support for all IRS statements and schedules
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import os
from collections import defaultdict
import re

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def parse_month_to_yyyymm(month_str: str) -> str:
    """
    Convert month string to YYYYMM format.
    Handles both "YYYYMM" format and "Month YYYY" format like "April 2026".
    """
    if not month_str or not month_str.strip():
        return "202507"  # Default fallback
    
    month_str = month_str.strip()
    
    # If already in YYYYMM format (6 digits), return as-is
    if re.match(r'^\d{6}$', month_str):
        return month_str
    
    # Month name mapping
    month_names = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    # Try to parse "Month YYYY" format
    for month_name, month_num in month_names.items():
        if month_name in month_str.lower():
            # Extract year from the string
            year_match = re.search(r'\b(20\d{2})\b', month_str)
            if year_match:
                year = year_match.group(1)
                return f"{year}{month_num}"
    
    # Fallback: try to extract any 6-digit number
    yyyymm_match = re.search(r'\b(\d{6})\b', month_str)
    if yyyymm_match:
        return yyyymm_match.group(1)
    
    # Default fallback
    print(f"⚠️ Warning: Could not parse month '{month_str}', using July 2025")
    return "202507"

# Static tax tables - Annual rates (July only)
WEIGHT_RATES = {
    "A": 100.00, "B": 122.00, "C": 144.00, "D": 166.00, "E": 188.00, "F": 210.00,
    "G": 232.00, "H": 254.00, "I": 276.00, "J": 298.00, "K": 320.00, "L": 342.00,
    "M": 364.00, "N": 386.00, "O": 408.00, "P": 430.00, "Q": 452.00, "R": 474.00,
    "S": 496.00, "T": 518.00, "U": 540.00, "V": 550.00, "W": 0.00
}
LOGGING_RATES = {
    "A": 75.0, "B": 91.5, "C": 108.0, "D": 124.5, "E": 141.0, "F": 157.5,
    "G": 174.0, "H": 190.5, "I": 207.0, "J": 223.5, "K": 240.0, "L": 256.5,
    "M": 273.0, "N": 289.5, "O": 306.0, "P": 322.5, "Q": 339.0, "R": 355.5,
    "S": 372.0, "T": 388.5, "U": 405.0, "V": 412.5, "W": 0.0
}

# IRS Partial-period tax tables (from official IRS Form 2290 instructions)
# Regular vehicles (non-logging) - Table I
PARTIAL_PERIOD_TAX_REGULAR = {
    "A": {8: 91.67, 9: 83.33, 10: 75.00, 11: 66.67, 12: 58.33, 1: 50.00, 2: 41.67, 3: 33.33, 4: 25.00, 5: 16.67, 6: 8.33},
    "B": {8: 111.83, 9: 101.67, 10: 91.50, 11: 81.33, 12: 71.17, 1: 61.00, 2: 50.83, 3: 40.67, 4: 30.50, 5: 20.33, 6: 10.17},
    "C": {8: 132.00, 9: 120.00, 10: 108.00, 11: 96.00, 12: 84.00, 1: 72.00, 2: 60.00, 3: 48.00, 4: 36.00, 5: 24.00, 6: 12.00},
    "D": {8: 152.17, 9: 138.33, 10: 124.50, 11: 110.67, 12: 96.83, 1: 83.00, 2: 69.17, 3: 55.33, 4: 41.50, 5: 27.67, 6: 13.83},
    "E": {8: 172.33, 9: 156.67, 10: 141.00, 11: 125.33, 12: 109.67, 1: 94.00, 2: 78.33, 3: 62.67, 4: 47.00, 5: 31.33, 6: 15.67},
    "F": {8: 192.50, 9: 175.00, 10: 157.50, 11: 140.00, 12: 122.50, 1: 105.00, 2: 87.50, 3: 70.00, 4: 52.50, 5: 35.00, 6: 17.50},
    "G": {8: 212.67, 9: 193.33, 10: 174.00, 11: 154.67, 12: 135.33, 1: 116.00, 2: 96.67, 3: 77.33, 4: 58.00, 5: 38.67, 6: 19.33},
    "H": {8: 232.83, 9: 211.67, 10: 190.50, 11: 169.33, 12: 148.17, 1: 127.00, 2: 105.83, 3: 84.67, 4: 63.50, 5: 42.33, 6: 21.17},
    "I": {8: 253.00, 9: 230.00, 10: 207.00, 11: 184.00, 12: 161.00, 1: 138.00, 2: 115.00, 3: 92.00, 4: 69.00, 5: 46.00, 6: 23.00},
    "J": {8: 273.17, 9: 248.33, 10: 223.50, 11: 198.67, 12: 173.83, 1: 149.00, 2: 124.17, 3: 99.33, 4: 74.50, 5: 49.67, 6: 24.83},
    "K": {8: 293.33, 9: 266.67, 10: 240.00, 11: 213.33, 12: 186.67, 1: 160.00, 2: 133.33, 3: 106.67, 4: 80.00, 5: 53.33, 6: 26.67},
    "L": {8: 313.50, 9: 285.00, 10: 256.50, 11: 228.00, 12: 199.50, 1: 171.00, 2: 142.50, 3: 114.00, 4: 85.50, 5: 57.00, 6: 28.50},
    "M": {8: 333.67, 9: 303.33, 10: 273.00, 11: 242.67, 12: 212.33, 1: 182.00, 2: 151.67, 3: 121.33, 4: 91.00, 5: 60.67, 6: 30.33},
    "N": {8: 353.83, 9: 321.67, 10: 289.50, 11: 257.33, 12: 225.17, 1: 193.00, 2: 160.83, 3: 128.67, 4: 96.50, 5: 64.33, 6: 32.17},
    "O": {8: 374.00, 9: 340.00, 10: 306.00, 11: 272.00, 12: 238.00, 1: 204.00, 2: 170.00, 3: 136.00, 4: 102.00, 5: 68.00, 6: 34.00},
    "P": {8: 394.17, 9: 358.33, 10: 322.50, 11: 286.67, 12: 250.83, 1: 215.00, 2: 179.17, 3: 143.33, 4: 107.50, 5: 71.67, 6: 35.83},
    "Q": {8: 414.33, 9: 376.67, 10: 339.00, 11: 301.33, 12: 263.67, 1: 226.00, 2: 188.33, 3: 150.67, 4: 113.00, 5: 75.33, 6: 37.67},
    "R": {8: 434.50, 9: 395.00, 10: 355.50, 11: 316.00, 12: 276.50, 1: 237.00, 2: 197.50, 3: 158.00, 4: 118.50, 5: 79.00, 6: 39.50},
    "S": {8: 454.67, 9: 413.33, 10: 372.00, 11: 330.67, 12: 289.33, 1: 248.00, 2: 206.67, 3: 165.33, 4: 124.00, 5: 82.67, 6: 41.33},
    "T": {8: 474.83, 9: 431.67, 10: 388.50, 11: 345.33, 12: 302.17, 1: 259.00, 2: 215.83, 3: 172.67, 4: 129.50, 5: 86.33, 6: 43.17},
    "U": {8: 495.00, 9: 450.00, 10: 405.00, 11: 360.00, 12: 315.00, 1: 270.00, 2: 225.00, 3: 180.00, 4: 135.00, 5: 90.00, 6: 45.00},
    "V": {8: 504.17, 9: 458.33, 10: 412.50, 11: 366.67, 12: 320.83, 1: 275.00, 2: 229.17, 3: 183.33, 4: 137.50, 5: 91.67, 6: 45.83},
    "W": {8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0}
}

# Logging vehicles (reduced rates) - Table II
PARTIAL_PERIOD_TAX_LOGGING = {
    "A": {8: 68.75, 9: 62.49, 10: 56.25, 11: 50.00, 12: 43.74, 1: 37.50, 2: 31.25, 3: 24.99, 4: 18.75, 5: 12.50, 6: 6.24},
    "B": {8: 83.87, 9: 76.25, 10: 68.62, 11: 60.99, 12: 53.37, 1: 45.75, 2: 38.12, 3: 30.50, 4: 22.87, 5: 15.24, 6: 7.62},
    "C": {8: 99.00, 9: 90.00, 10: 81.00, 11: 72.00, 12: 63.00, 1: 54.00, 2: 45.00, 3: 36.00, 4: 27.00, 5: 18.00, 6: 9.00},
    "D": {8: 114.12, 9: 103.74, 10: 93.37, 11: 83.00, 12: 72.62, 1: 62.25, 2: 51.87, 3: 41.49, 4: 31.12, 5: 20.75, 6: 10.37},
    "E": {8: 129.24, 9: 117.50, 10: 105.75, 11: 93.99, 12: 82.25, 1: 70.50, 2: 58.74, 3: 47.00, 4: 35.25, 5: 23.49, 6: 11.75},
    "F": {8: 144.37, 9: 131.25, 10: 118.12, 11: 105.00, 12: 91.87, 1: 78.75, 2: 65.62, 3: 52.50, 4: 39.37, 5: 26.25, 6: 13.12},
    "G": {8: 159.50, 9: 144.99, 10: 130.50, 11: 116.00, 12: 101.49, 1: 87.00, 2: 72.50, 3: 57.99, 4: 43.50, 5: 29.00, 6: 14.49},
    "H": {8: 174.62, 9: 158.75, 10: 142.87, 11: 126.99, 12: 111.12, 1: 95.25, 2: 79.37, 3: 63.50, 4: 47.62, 5: 31.74, 6: 15.87},
    "I": {8: 189.75, 9: 172.50, 10: 155.25, 11: 138.00, 12: 120.75, 1: 103.50, 2: 86.25, 3: 69.00, 4: 51.75, 5: 34.50, 6: 17.25},
    "J": {8: 204.87, 9: 186.24, 10: 167.62, 11: 149.00, 12: 130.37, 1: 111.75, 2: 93.12, 3: 74.49, 4: 55.87, 5: 37.25, 6: 18.62},
    "K": {8: 219.99, 9: 200.00, 10: 180.00, 11: 159.99, 12: 140.00, 1: 120.00, 2: 99.99, 3: 80.00, 4: 60.00, 5: 39.99, 6: 20.00},
    "L": {8: 235.12, 9: 213.75, 10: 192.37, 11: 171.00, 12: 149.62, 1: 128.25, 2: 106.87, 3: 85.50, 4: 64.12, 5: 42.75, 6: 21.37},
    "M": {8: 250.25, 9: 227.49, 10: 204.75, 11: 182.00, 12: 159.24, 1: 136.50, 2: 113.75, 3: 90.99, 4: 68.25, 5: 45.50, 6: 22.74},
    "N": {8: 265.37, 9: 241.25, 10: 217.12, 11: 192.99, 12: 168.87, 1: 144.75, 2: 120.62, 3: 96.50, 4: 72.37, 5: 48.24, 6: 24.12},
    "O": {8: 280.50, 9: 255.00, 10: 229.50, 11: 204.00, 12: 178.50, 1: 153.00, 2: 127.50, 3: 102.00, 4: 76.50, 5: 51.00, 6: 25.50},
    "P": {8: 295.62, 9: 268.74, 10: 241.87, 11: 215.00, 12: 188.12, 1: 161.25, 2: 134.37, 3: 107.49, 4: 80.62, 5: 53.75, 6: 26.87},
    "Q": {8: 310.74, 9: 282.50, 10: 254.25, 11: 225.99, 12: 197.75, 1: 169.50, 2: 141.24, 3: 113.00, 4: 84.75, 5: 56.49, 6: 28.25},
    "R": {8: 325.87, 9: 296.25, 10: 266.62, 11: 237.00, 12: 207.37, 1: 177.75, 2: 148.12, 3: 118.50, 4: 88.87, 5: 59.25, 6: 29.62},
    "S": {8: 341.00, 9: 309.99, 10: 279.00, 11: 248.00, 12: 216.99, 1: 186.00, 2: 155.00, 3: 123.99, 4: 93.00, 5: 62.00, 6: 30.99},
    "T": {8: 356.12, 9: 323.75, 10: 291.37, 11: 258.99, 12: 226.62, 1: 194.25, 2: 161.87, 3: 129.50, 4: 97.12, 5: 64.74, 6: 32.37},
    "U": {8: 371.25, 9: 337.50, 10: 303.75, 11: 270.00, 12: 236.25, 1: 202.50, 2: 168.75, 3: 135.00, 4: 101.25, 5: 67.50, 6: 33.75},
    "V": {8: 378.12, 9: 343.74, 10: 309.37, 11: 275.00, 12: 240.62, 1: 206.25, 2: 171.87, 3: 137.49, 4: 103.12, 5: 68.75, 6: 34.37},
    "W": {8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0}
}

def build_supporting_statements(data: dict, return_data: ET.Element) -> None:
    """Build all supporting statements based on form data"""
    vehicles = data.get("vehicles", [])
    
    # 1. Credits Amount Statement (for disposals)
    disposal_vehicles = [v for v in vehicles if v.get("disposal_date")]
    if disposal_vehicles or data.get("tax_credits", 0) > 0:
        credits_stmt = ET.SubElement(return_data, "CreditsAmountStatement")
        credits_info = ET.SubElement(credits_stmt, "CreditsAmountInfo")
        
        for vehicle in disposal_vehicles:
            disposal_item = ET.SubElement(credits_info, "DisposalReportingItem")
            
            explanation = f"Vehicle disposed - {vehicle.get('disposal_reason', 'N/A')}"
            ET.SubElement(disposal_item, "CreditsAmountExplanationTxt").text = explanation
            ET.SubElement(disposal_item, "DisposalReportingVIN").text = vehicle.get("vin", "")
            ET.SubElement(disposal_item, "DisposalReportingDt").text = vehicle.get("disposal_date", "")
            
            disposal_amount = vehicle.get("disposal_amount", 0)
            if disposal_amount:
                ET.SubElement(disposal_item, "DisposalReportingAmt").text = f"{float(disposal_amount):.2f}"
    
    # 2. Suspended VIN Statement
    suspended_vehicles = [v for v in vehicles if v.get("is_suspended") or v.get("is_agricultural")]
    if suspended_vehicles:
        suspended_stmt = ET.SubElement(return_data, "SuspendedVINStatement")
        suspended_info = ET.SubElement(suspended_stmt, "SuspendedVINInfo")
        
        for vehicle in suspended_vehicles:
            vin_detail = ET.SubElement(suspended_info, "VINDetail")
            ET.SubElement(vin_detail, "VIN").text = vehicle.get("vin", "")
    
    # 3. Private Sale Vehicle Statement
    private_sale_vehicles = [v for v in vehicles if v.get("sale_to_private_party")]
    if private_sale_vehicles:
        private_sale_stmt = ET.SubElement(return_data, "PrivateSaleVehicleStatement")
        private_sale_info = ET.SubElement(private_sale_stmt, "PrivateSaleVehicleInfo")
        
        # Group by business (assuming same business for all)
        name_address = ET.SubElement(private_sale_info, "NameAndAddress")
        ET.SubElement(name_address, "BusinessNameLine1Txt").text = data.get("business_name", "")
        
        address_group = ET.SubElement(name_address, "USAddress")
        ET.SubElement(address_group, "AddressLine1Txt").text = data.get("address", "")[:35]
        ET.SubElement(address_group, "CityNm").text = data.get("city", "")
        ET.SubElement(address_group, "StateAbbreviationCd").text = data.get("state", "")
        ET.SubElement(address_group, "ZIPCd").text = data.get("zip", "")
        
        for vehicle in private_sale_vehicles:
            ET.SubElement(private_sale_info, "VIN").text = vehicle.get("vin", "")
    
    # 4. TGW Increase Worksheet
    tgw_vehicles = [v for v in vehicles if v.get("tgw_increased")]
    if tgw_vehicles:
        tgw_stmt = ET.SubElement(return_data, "TGWIncreaseWorksheet")
        
        for vehicle in tgw_vehicles:
            tgw_info = ET.SubElement(tgw_stmt, "TGWIncreaseInfo")
            
            increase_month = vehicle.get("tgw_increase_month", "")
            if len(increase_month) >= 6:
                month_num = int(increase_month[-2:]) if increase_month[-2:].isdigit() else 7
                ET.SubElement(tgw_info, "TGWIncreaseMonthNum").text = str(month_num)
            
            current_category = vehicle.get("category", "")
            previous_category = vehicle.get("tgw_previous_category", "")
            
            ET.SubElement(tgw_info, "TGWCategoryCd").text = current_category
            
            # Calculate tax amounts
            new_rate = WEIGHT_RATES.get(current_category, 0.0)
            previous_rate = WEIGHT_RATES.get(previous_category, 0.0)
            
            ET.SubElement(tgw_info, "NewTaxAmt").text = f"{new_rate:.2f}"
            ET.SubElement(tgw_info, "PreviousTaxAmt").text = f"{previous_rate:.2f}"
            ET.SubElement(tgw_info, "AdditionalTaxAmt").text = f"{max(0, new_rate - previous_rate):.2f}"
    
    # 5. VIN Correction Explanation Statement
    if data.get("vin_correction") and data.get("vin_correction_explanation"):
        vin_correction_stmt = ET.SubElement(return_data, "VINCorrectionExplanationStmt")
        ET.SubElement(vin_correction_stmt, "ExplanationTxt").text = data.get("vin_correction_explanation", "")
    
    # 6. Reasonable Cause Explanation (for amendments)
    if data.get("amended_return") and data.get("reasonable_cause_explanation"):
        reasonable_cause_stmt = ET.SubElement(return_data, "ReasonableCauseExpln")
        ET.SubElement(reasonable_cause_stmt, "ExplanationTxt").text = data.get("reasonable_cause_explanation", "")
    
    # 7. Statement in Support of Suspension
    if suspended_vehicles:
        suspension_stmt = ET.SubElement(return_data, "StmtInSupportOfSuspension")
        suspension_info = ET.SubElement(suspension_stmt, "StmtInSupportOfSuspensionInfo")
        
        for vehicle in suspended_vehicles:
            suspension_detail = ET.SubElement(suspension_info, "VehicleSuspensionDetail")
            ET.SubElement(suspension_detail, "VIN").text = vehicle.get("vin", "")
            ET.SubElement(suspension_detail, "BusinessName").text = data.get("business_name", "")
            ET.SubElement(suspension_detail, "Dt").text = datetime.now().strftime("%Y-%m-%d")
    
    # 8. General Dependency Medium (for additional attachments)
    # This handles the GeneralDependencyMedium.xsd schema for custom attachments
    if data.get("additional_attachments"):
        for attachment in data.get("additional_attachments", []):
            general_dep = ET.SubElement(return_data, "GeneralDependencyMedium")
            
            # Business or person name
            if attachment.get("business_name"):
                ET.SubElement(general_dep, "BusinessName").text = attachment.get("business_name")
            elif attachment.get("person_name"):
                ET.SubElement(general_dep, "PersonNm").text = attachment.get("person_name")
            
            # Tax ID
            if attachment.get("ein"):
                ET.SubElement(general_dep, "EIN").text = attachment.get("ein")
            elif attachment.get("ssn"):
                ET.SubElement(general_dep, "SSN").text = attachment.get("ssn")
            elif attachment.get("missing_ein_reason"):
                ET.SubElement(general_dep, "MissingEINReasonCd").text = attachment.get("missing_ein_reason")
            
            # Form line reference
            if attachment.get("form_line_reference"):
                ET.SubElement(general_dep, "FormLineOrInstructionRefTxt").text = attachment.get("form_line_reference")
            
            # Regulations reference
            if attachment.get("regulation_reference"):
                ET.SubElement(general_dep, "RegulationReferenceTxt").text = attachment.get("regulation_reference")
            
            # Description
            if attachment.get("description"):
                ET.SubElement(general_dep, "Desc").text = attachment.get("description")
            
            # Detailed attachment information
            if attachment.get("attachment_information"):
                ET.SubElement(general_dep, "AttachmentInformationMedDesc").text = attachment.get("attachment_information")


def build_enhanced_payment_record(data: dict, return_data: ET.Element) -> None:
    """Build enhanced IRSPayment2 record"""
    if data.get("payEFTPS") and data.get("eftps_routing") and data.get("eftps_account"):
        payment = ET.SubElement(return_data, "IRSPayment2")
        
        ET.SubElement(payment, "RoutingTransitNum").text = data.get("eftps_routing", "")
        ET.SubElement(payment, "BankAccountNum").text = data.get("eftps_account", "")
        ET.SubElement(payment, "BankAccountTypeCd").text = data.get("account_type", "Checking")
        
        # Calculate payment amount (total tax minus credits)
        vehicles = data.get("vehicles", [])
        current_month = data.get("current_month")  # Should be passed when generating by month
        total_tax = 0.0
        for vehicle in vehicles:
            # Only include vehicles for this specific month if generating separate files
            if current_month and vehicle.get("used_month") != current_month:
                continue
                
            total_tax += calculate_vehicle_tax(vehicle)
        
        credits = float(data.get("tax_credits", 0.0))
        payment_amount = max(0.0, total_tax - credits)
        
        ET.SubElement(payment, "PaymentAmt").text = f"{payment_amount:.2f}"
        ET.SubElement(payment, "RequestedPaymentDt").text = data.get("payment_date", datetime.now().strftime("%Y-%m-%d"))
        ET.SubElement(payment, "TaxpayerDaytimePhoneNum").text = data.get("taxpayer_phone", "")


def validate_business_rules(data: dict) -> list:
    """
    Validate Form 2290 against IRS business rules
    Returns list of validation errors
    """
    errors = []
    vehicles = data.get("vehicles", [])
    
    # F2290-003-01: If Line 3 (TGW increase) has value, amended return must be checked
    tgw_vehicles = [v for v in vehicles if v.get("tgw_increased")]
    if tgw_vehicles and not data.get("amended_return"):
        errors.append("F2290-003-01: Amended return must be checked when TGW increase is present")
    
    # F2290-004-01: Line 5 (credits) cannot be more than Line 4 (total tax)
    total_tax = calculate_total_tax(vehicles)
    credits = float(data.get("tax_credits", 0))
    if credits > 0 and credits > total_tax:
        errors.append("F2290-004-01: Credits amount cannot exceed total tax")
    
    # F2290-008-01: If 5000 mile checkbox checked, Category W must have positive value
    mileage_vehicles = [v for v in vehicles if v.get("mileage_5000_or_less")]
    if mileage_vehicles:
        w_category_count = len([v for v in vehicles if v.get("category") == "W"])
        if w_category_count == 0:
            errors.append("F2290-008-01: Category W vehicles required when 5000 mile limit is checked")
    
    # F2290-027-01: If not final return, must have at least one VIN
    if not data.get("final_return") and not vehicles:
        errors.append("F2290-027-01: At least one VIN required unless final return")
    
    # F2290-032-01: If VIN correction checked, must have at least one VIN
    if data.get("vin_correction") and not vehicles:
        errors.append("F2290-032-01: At least one VIN required when VIN correction is checked")
    
    # F2290-033-01: If amended return checked, must have at least one VIN
    if data.get("amended_return") and not vehicles:
        errors.append("F2290-033-01: At least one VIN required for amended returns")
    
    # F2290-068: If balance due > 0, payment method must be selected
    balance_due = max(0, total_tax - credits)
    if balance_due > 0:
        if not data.get("payEFTPS") and not data.get("payCard"):
            errors.append("F2290-068: Payment method required when balance due > 0")
    
    # R0000-084-01: Taxpayer PIN validation for online filers
    pin = data.get("taxpayer_pin", "")
    if pin and pin == "00000":
        errors.append("R0000-084-01: Taxpayer PIN cannot be all zeros")
    
    # VIN duplicate validation (F2290-017)
    vins = [v.get("vin", "").strip().upper() for v in vehicles if v.get("vin")]
    if len(vins) != len(set(vins)):
        errors.append("F2290-017: Duplicate VINs not allowed")
    
    return errors

def calculate_vehicle_tax(vehicle: dict) -> float:
    """Calculate tax for a single vehicle using IRS lookup tables"""
    if vehicle.get("is_suspended") or vehicle.get("is_agricultural"):
        return 0.0
    
    cat = vehicle.get("category", "")
    used = vehicle.get("used_month", "")
    logging = bool(vehicle.get("is_logging"))
    
    if not cat or cat not in WEIGHT_RATES:
        return 0.0
    
    if len(used) >= 6:
        mon = int(used[-2:]) if used[-2:].isdigit() else 7
    else:
        mon = 7
    
    # July (month 7) = annual tax
    if mon == 7:
        if logging:
            return LOGGING_RATES.get(cat, 0.0)
        else:
            return WEIGHT_RATES.get(cat, 0.0)
    else:
        # All other months = partial-period tax using lookup tables
        if logging:
            return PARTIAL_PERIOD_TAX_LOGGING.get(cat, {}).get(mon, 0.0)
        else:
            return PARTIAL_PERIOD_TAX_REGULAR.get(cat, {}).get(mon, 0.0)

def calculate_total_tax(vehicles: list) -> float:
    """Calculate total tax for vehicles using IRS lookup tables"""
    total = 0.0
    for vehicle in vehicles:
        total += calculate_vehicle_tax(vehicle)
    return round(total, 2)

def build_2290_xml(data: dict) -> str:
    """Build IRS-compliant Form 2290 XML according to 2025v1.0 schema"""
    
    # Validate business rules first
    validation_errors = validate_business_rules(data)
    if validation_errors:
        error_msg = "IRS Business Rule Violations:\n" + "\n".join(validation_errors)
        raise ValueError(error_msg)
    
    # Create root Return element with namespace and version
    root = ET.Element("Return")
    root.set("xmlns", "http://www.irs.gov/efile")
    root.set("returnVersion", "2025v1.0")

    
    # ── Return Header ─────────────────────────────────────
    return_header = ET.SubElement(root, "ReturnHeader")
    return_header.set("binaryAttachmentCnt", "0")
    
    # Return timestamp
    ET.SubElement(return_header, "ReturnTs").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # First used date (from data or July 1st of tax year)
    first_used = data.get("used_on_july", f"{data.get('tax_year', '2025')}-07-01")
    if len(first_used) >= 7:  # YYYY-MM format required
        first_used_formatted = first_used[:7]  # Take YYYY-MM part
    else:
        first_used_formatted = f"{data.get('tax_year', '2025')}-07"
    ET.SubElement(return_header, "FirstUsedDt").text = first_used_formatted
    
    # Software identification (required) - From environment variable
    software_id = os.getenv('IRS_SOFTWARE_ID', '38720501')  # Default fallback
    ET.SubElement(return_header, "SoftwareId").text = software_id
    ET.SubElement(return_header, "MultSoftwarePackagesUsedInd").text = "false"
    
    # Originator group (required for e-file) - From environment variable
    originator = ET.SubElement(return_header, "OriginatorGrp")
    efin = os.getenv('IRS_EFIN', '387205')  # Default fallback
    ET.SubElement(originator, "EFIN").text = efin
    ET.SubElement(originator, "OriginatorTypeCd").text = "OnlineFilerSelfSelect"
    
    # Return type
    ET.SubElement(return_header, "ReturnTypeCd").text = "2290"
    
    # Filer information
    filer = ET.SubElement(return_header, "Filer")
    taxpayer_ein = data.get("ein", "").replace("-", "").zfill(9)
    ET.SubElement(filer, "EIN").text = taxpayer_ein
    ET.SubElement(filer, "BusinessNameLine1Txt").text = data.get("business_name", "")[:60]  # Max 60 chars
    
    # Optional second business name line
    if data.get("business_name_line2"):
        ET.SubElement(filer, "BusinessNameLine2Txt").text = data.get("business_name_line2", "")[:60]
    
    # Business name control (first 4 chars of business name, uppercase)
    business_name = data.get("business_name", "")
    name_control = ''.join(c for c in business_name.upper() if c.isalpha())[:4].ljust(4, 'X')
    ET.SubElement(filer, "BusinessNameControlTxt").text = name_control
    
    # Address (IRS requirement: max 35 chars per line)
    us_address = ET.SubElement(filer, "USAddress")
    ET.SubElement(us_address, "AddressLine1Txt").text = data.get("address", "")[:35]  # Enforce 35 char limit
    if data.get("address_line2"):
        ET.SubElement(us_address, "AddressLine2Txt").text = data.get("address_line2", "")[:35]  # Enforce 35 char limit
    ET.SubElement(us_address, "CityNm").text = data.get("city", "")
    ET.SubElement(us_address, "StateAbbreviationCd").text = data.get("state", "")
    ET.SubElement(us_address, "ZIPCd").text = data.get("zip", "")
    
    # Business officer (required for e-filing signature)
    officer_name = data.get("officer_name", "").strip()
    if not officer_name:
        # Fallback to signature fields if officer fields not provided
        officer_name = data.get("printed_name", "").strip()
    
    if officer_name:
        officer = ET.SubElement(return_header, "BusinessOfficerGrp")
        ET.SubElement(officer, "PersonNm").text = officer_name
        
        # Officer SSN (required by IRS for e-filing)
        officer_ssn = data.get("officer_ssn", "").replace("-", "").zfill(9)
        if officer_ssn and officer_ssn != "000000000":
            ET.SubElement(officer, "PersonSSN").text = officer_ssn
        
        officer_title = data.get("officer_title", "").strip()
        if not officer_title:
            officer_title = "Owner"  # Default title if not provided
        ET.SubElement(officer, "PersonTitleTxt").text = officer_title
        ET.SubElement(officer, "SignatureDt").text = datetime.now().strftime("%Y-%m-%d")
    
    # PIN authentication for e-filing
    taxpayer_pin = data.get("taxpayer_pin", "").strip()
    if taxpayer_pin:
        pin_group = ET.SubElement(return_header, "PINEntryTypeCd")
        pin_group.text = "Self-Select PIN"
        # Note: Actual PIN is not stored in XML for security - handled by e-filing system
    
    # Preparer information
    if data.get("preparer_name"):
        preparer = ET.SubElement(return_header, "PreparerPersonGrp")
        ET.SubElement(preparer, "PreparerPersonNm").text = data.get("preparer_name", "")
        ET.SubElement(preparer, "PTIN").text = data.get("preparer_ptin", "")
        
        # Self-employed indicator (required by IRS)
        if data.get("preparer_self_employed", True):  # Default to True if not specified
            ET.SubElement(preparer, "SelfEmployedInd").text = "X"
        
        # Use preparer firm phone number for preparer phone (IRS allows this)
        preparer_phone = data.get("preparer_firm_phone", "").replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
        if preparer_phone:
            ET.SubElement(preparer, "PhoneNum").text = preparer_phone
        
        if data.get("date_prepared"):
            ET.SubElement(preparer, "PreparationDt").text = data.get("date_prepared", "")
    
    # Preparer firm - Software developer information from environment
    firm = ET.SubElement(return_header, "PreparerFirmGrp")
    developer_ein = os.getenv('DEVELOPER_EIN', '334623152')  # Default fallback
    ET.SubElement(firm, "PreparerFirmEIN").text = developer_ein
    developer_name = os.getenv('DEVELOPER_NAME', 'Majd Consulting, PLLC')
    ET.SubElement(firm, "PreparerFirmName").text = developer_name
    
    # Developer business address from environment
    firm_address = ET.SubElement(firm, "PreparerUSAddress")
    developer_address = os.getenv('DEVELOPER_ADDRESS', '18673 Audette St')
    developer_city = os.getenv('DEVELOPER_CITY', 'Dearborn')
    developer_state = os.getenv('DEVELOPER_STATE', 'MI')
    developer_zip = os.getenv('DEVELOPER_ZIP', '48124')
    
    ET.SubElement(firm_address, "AddressLine1Txt").text = developer_address
    ET.SubElement(firm_address, "CityNm").text = developer_city
    ET.SubElement(firm_address, "StateAbbreviationCd").text = developer_state
    ET.SubElement(firm_address, "ZIPCd").text = developer_zip
    
    # Additional preparer firm from user input (if different from developer)
    if data.get("preparer_firm_name") and data.get("preparer_firm_name") != developer_name:
        additional_firm = ET.SubElement(return_header, "PreparerFirmGrp")
        firm_ein = data.get("preparer_firm_ein", "").replace("-", "").zfill(9)
        ET.SubElement(additional_firm, "PreparerFirmEIN").text = firm_ein
        ET.SubElement(additional_firm, "PreparerFirmName").text = data.get("preparer_firm_name", "")
        
        additional_firm_address = ET.SubElement(additional_firm, "PreparerUSAddress")
        ET.SubElement(additional_firm_address, "AddressLine1Txt").text = data.get("preparer_firm_address", "")
        firm_city_state_zip = data.get("preparer_firm_citystatezip", "").split(", ")
        if len(firm_city_state_zip) >= 2:
            ET.SubElement(additional_firm_address, "CityNm").text = firm_city_state_zip[0]
            state_zip = firm_city_state_zip[1].split(" ")
            if len(state_zip) >= 2:
                ET.SubElement(additional_firm_address, "StateAbbreviationCd").text = state_zip[0]
                ET.SubElement(additional_firm_address, "ZIPCd").text = state_zip[1]
    
    # Third party designee
    if data.get("designee_name"):
        designee = ET.SubElement(return_header, "ThirdPartyDesignee")
        ET.SubElement(designee, "DiscussWithThirdPartyYesInd").text = "X"
        ET.SubElement(designee, "ThirdPartyDesigneeNm").text = data.get("designee_name", "")
        ET.SubElement(designee, "ThirdPartyDesigneePhoneNum").text = data.get("designee_phone", "")
        ET.SubElement(designee, "ThirdPartyDesigneePIN").text = data.get("designee_pin", "")
    
    # Consent to VIN data disclosure
    consent_group = ET.SubElement(return_header, "ConsentToVINDataDisclosureGrp")
    if data.get("consent_to_disclose"):
        ET.SubElement(consent_group, "ConsentToDiscloseYesInd").text = "X"
        disclosure_info = ET.SubElement(consent_group, "DisclosureFormSignatureInfo")
        ET.SubElement(consent_group, "SignatureOptionCd").text = "PIN Number"
    else:
        ET.SubElement(consent_group, "ConsentToDiscloseNoInd").text = "X"
    
    # Tax year
    ET.SubElement(return_header, "TaxYr").text = str(data.get("tax_year", "2025"))
    
    # ── Return Data ───────────────────────────────────────
    return_data = ET.SubElement(root, "ReturnData")
    
    # ── IRS2290 Form ─────────────────────────────────────
    form_2290 = ET.SubElement(return_data, "IRS2290")
    
    # Form indicators
    if data.get("address_change"):
        ET.SubElement(form_2290, "AddressChangeInd").text = "X"
    if data.get("amended_return"):
        ET.SubElement(form_2290, "AmendedReturnInd").text = "X"
        # Add amended month if provided
        if data.get("amended_month"):
            amended_month_raw = data.get("amended_month", "")
            amended_month = parse_month_to_yyyymm(amended_month_raw)
            if len(amended_month) >= 6:
                month_num = int(amended_month[-2:]) if amended_month[-2:].isdigit() else 11
                ET.SubElement(form_2290, "AmendedMonthNum").text = str(month_num)
    if data.get("vin_correction"):
        ET.SubElement(form_2290, "VINCorrectionInd").text = "X"
    if data.get("final_return"):
        ET.SubElement(form_2290, "FinalReturnInd").text = "X"
    
    # Special conditions
    if data.get("special_conditions"):
        ET.SubElement(form_2290, "SpecialConditionDesc").text = data.get("special_conditions", "")
    
    # Calculate tax computation by category
    vehicles = data.get("vehicles", [])
    category_data = defaultdict(lambda: {"non_logging_count": 0, "logging_count": 0, "non_logging_tax": 0.0, "logging_tax": 0.0})
    total_tax = 0.0
    
    for vehicle in vehicles:
        cat = vehicle.get("category", "").strip()
        used = vehicle.get("used_month", "").strip()
        logging = bool(vehicle.get("is_logging"))
        suspended = bool(vehicle.get("is_suspended") or vehicle.get("is_agricultural"))
        
        if suspended:
            continue  # Don't include suspended vehicles in tax computation
            
        # Calculate tax using lookup tables
        tax_amount = calculate_vehicle_tax(vehicle)
        
        if logging:
            category_data[cat]["logging_count"] += 1
            category_data[cat]["logging_tax"] += tax_amount
        else:
            category_data[cat]["non_logging_count"] += 1
            category_data[cat]["non_logging_tax"] += tax_amount
        
        total_tax += tax_amount
    
    # Add tax computation groups for each category
    for category, data_cat in sorted(category_data.items()):
        if data_cat["non_logging_count"] > 0 or data_cat["logging_count"] > 0:
            comp_group = ET.SubElement(form_2290, "HighwayMtrVehTxComputationGrp")
            ET.SubElement(comp_group, "VehicleCategoryCd").text = category
            
            columns = ET.SubElement(comp_group, "HighwayMtrVehTxCmptColumnsGrp")
            
            if data_cat["non_logging_count"] > 0:
                ET.SubElement(columns, "NonLoggingVehPartialTaxAmt").text = f"{WEIGHT_RATES.get(category, 0.0):.2f}"
                ET.SubElement(columns, "NonLoggingVehicleCnt").text = str(data_cat["non_logging_count"])
            
            if data_cat["logging_count"] > 0:
                ET.SubElement(columns, "LoggingVehPartialTaxAmt").text = f"{LOGGING_RATES.get(category, 0.0):.2f}"
                ET.SubElement(columns, "LoggingVehicleCnt").text = str(data_cat["logging_count"])
            
            category_total = data_cat["non_logging_tax"] + data_cat["logging_tax"]
            ET.SubElement(columns, "TaxAmt").text = f"{category_total:.2f}"
    
    # Total calculations
    total_vehicles = len([v for v in vehicles if not v.get("is_suspended")])
    if total_vehicles > 0:
        ET.SubElement(form_2290, "TotalVehicleCnt").text = str(total_vehicles)
    if total_tax > 0:
        ET.SubElement(form_2290, "TotalTaxComputationAmt").text = f"{total_tax:.2f}"
    
    # Suspended vehicle counts (enhanced)
    suspended_non_logging = len([v for v in vehicles if v.get("is_suspended") and not v.get("is_logging")])
    suspended_logging = len([v for v in vehicles if v.get("is_suspended") and v.get("is_logging")])
    
    if suspended_non_logging > 0:
        ET.SubElement(form_2290, "TaxSuspendedNonLoggingVehCnt").text = str(suspended_non_logging)
    if suspended_logging > 0:
        ET.SubElement(form_2290, "TaxSuspendedLoggingVehCnt").text = str(suspended_logging)
    
    # Balance due (after any credits)
    credits = float(data.get("tax_credits", 0.0))
    balance_due = max(0.0, total_tax - credits)
    ET.SubElement(form_2290, "BalanceDueAmt").text = f"{balance_due:.2f}"
    
    # Add credits amount if provided
    if credits > 0:
        ET.SubElement(form_2290, "TaxCreditsAmt").text = f"{credits:.2f}"
    
    # Payment method
    if data.get("payEFTPS"):
        ET.SubElement(form_2290, "EFTPSPaymentInd").text = "X"
    elif data.get("payCard"):
        ET.SubElement(form_2290, "CreditDebitCardPaymentInd").text = "X"
    
    # Mileage indicators (form level)
    if any(v.get("mileage_5000_or_less") for v in vehicles):
        ET.SubElement(form_2290, "MileageUsed5000OrLessInd").text = "X"
    if any(v.get("is_agricultural") for v in vehicles):
        ET.SubElement(form_2290, "AgricMileageUsed7500OrLessInd").text = "X"
    
    # ── IRS2290 Schedule 1 ───────────────────────────────
    schedule1 = ET.SubElement(return_data, "IRS2290Schedule1")
    
    # Vehicle report items
    for vehicle in vehicles:
        if vehicle.get("is_suspended"):
            continue  # Skip suspended vehicles for now (they go in a different section)
            
        item = ET.SubElement(schedule1, "VehicleReportTaxItem")
        
        vin = vehicle.get("vin", "").strip().upper()
        category = vehicle.get("category", "").strip().upper()
        
        ET.SubElement(item, "VIN").text = vin
        ET.SubElement(item, "VehicleCategoryCd").text = category
    
    # Summary counts
    total_reported = len([v for v in vehicles if not v.get("is_suspended")])
    total_suspended = len([v for v in vehicles if v.get("is_suspended")])
    
    if total_reported > 0:
        ET.SubElement(schedule1, "VehicleCnt").text = str(total_reported + total_suspended)
    if total_suspended > 0:
        ET.SubElement(schedule1, "TotalSuspendedVehicleCnt").text = str(total_suspended)
    if total_reported > 0:
        ET.SubElement(schedule1, "TaxableVehicleCnt").text = str(total_reported)

    # ── Build Supporting Statements ─────────────────────
    build_supporting_statements(data, return_data)
    
    # ── Build Enhanced Payment Record ───────────────────
    build_enhanced_payment_record(data, return_data)
    
    # ── Return Pretty XML ───────────────────────────────
    rough = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")
