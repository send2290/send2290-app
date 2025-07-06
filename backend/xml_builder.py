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

# Static tax tables (Table I and Logging Table II)
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


def build_enhanced_payment_record(data: dict, return_data: ET.Element) -> None:
    """Build enhanced IRSPayment2 record"""
    if data.get("payEFTPS") and data.get("eftps_routing") and data.get("eftps_account"):
        payment = ET.SubElement(return_data, "IRSPayment2")
        
        ET.SubElement(payment, "RoutingTransitNum").text = data.get("eftps_routing", "")
        ET.SubElement(payment, "BankAccountNum").text = data.get("eftps_account", "")
        ET.SubElement(payment, "BankAccountTypeCd").text = data.get("account_type", "Checking")
        
        # Calculate payment amount (total tax minus credits)
        vehicles = data.get("vehicles", [])
        total_tax = 0.0
        for vehicle in vehicles:
            if vehicle.get("is_suspended") or vehicle.get("is_agricultural"):
                continue
            
            cat = vehicle.get("category", "")
            used = vehicle.get("used_month", "")
            logging = bool(vehicle.get("is_logging"))
            
            if len(used) >= 6:
                mon = int(used[-2:]) if used[-2:].isdigit() else 7
            else:
                mon = 7
            
            months_left = 12 if mon >= 7 else (13 - mon if 1 <= mon <= 12 else 0)
            
            if logging:
                rate = LOGGING_RATES.get(cat, 0.0)
            else:
                rate = WEIGHT_RATES.get(cat, 0.0)
            
            total_tax += round(rate * (months_left / 12), 2)
        
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

def calculate_total_tax(vehicles: list) -> float:
    """Calculate total tax for vehicles (helper function)"""
    total = 0.0
    for vehicle in vehicles:
        if vehicle.get("is_suspended") or vehicle.get("is_agricultural"):
            continue
        
        cat = vehicle.get("category", "")
        used = vehicle.get("used_month", "")
        logging = bool(vehicle.get("is_logging"))
        
        if len(used) >= 6:
            mon = int(used[-2:]) if used[-2:].isdigit() else 7
        else:
            mon = 7
        
        months_left = 12 if mon >= 7 else (13 - mon if 1 <= mon <= 12 else 0)
        
        if logging:
            rate = LOGGING_RATES.get(cat, 0.0)
        else:
            rate = WEIGHT_RATES.get(cat, 0.0)
        
        total += round(rate * (months_left / 12), 2)
    
    return total

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
    
    # Software identification (required) - Your actual Software ID
    ET.SubElement(return_header, "SoftwareId").text = "38720501"
    ET.SubElement(return_header, "MultSoftwarePackagesUsedInd").text = "false"
    
    # Originator group (required for e-file) - Your actual EFIN
    originator = ET.SubElement(return_header, "OriginatorGrp")
    ET.SubElement(originator, "EFIN").text = "387205"  # Your EFIN
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
    
    # Preparer firm - Always include your business as the software developer
    firm = ET.SubElement(return_header, "PreparerFirmGrp")
    ET.SubElement(firm, "PreparerFirmEIN").text = "334623152"  # Your EIN: 33-4623152
    ET.SubElement(firm, "PreparerFirmName").text = "Majd Consulting, PLLC"
    
    # Your business address
    firm_address = ET.SubElement(firm, "PreparerUSAddress")
    ET.SubElement(firm_address, "AddressLine1Txt").text = "18673 Audette St"
    ET.SubElement(firm_address, "CityNm").text = "Dearborn"
    ET.SubElement(firm_address, "StateAbbreviationCd").text = "MI"
    ET.SubElement(firm_address, "ZIPCd").text = "48124"
    
    # Additional preparer firm from user input (if different from your business)
    if data.get("preparer_firm_name") and data.get("preparer_firm_name") != "Majd Consulting, PLLC":
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
        suspended = bool(vehicle.get("is_suspended"))
        
        if suspended:
            continue  # Don't include suspended vehicles in tax computation
            
        # Calculate months from first use
        if len(used) >= 6:  # YYYYMM format
            mon = int(used[-2:]) if used[-2:].isdigit() else 7
        else:
            mon = 7  # Default to July
            
        months_left = 12 if mon >= 7 else (13 - mon if 1 <= mon <= 12 else 0)
        
        if logging:
            base_rate = LOGGING_RATES.get(cat, 0.0)
            tax_amount = round(base_rate * (months_left / 12), 2)
            category_data[cat]["logging_count"] += 1
            category_data[cat]["logging_tax"] += tax_amount
        else:
            base_rate = WEIGHT_RATES.get(cat, 0.0)
            tax_amount = round(base_rate * (months_left / 12), 2)
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
