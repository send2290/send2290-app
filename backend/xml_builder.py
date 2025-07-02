"""
IRS-compliant Form 2290 XML builder based on 2025v1.0 schema
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import os
from collections import defaultdict

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

def build_2290_xml(data: dict) -> str:
    """Build IRS-compliant Form 2290 XML according to 2025v1.0 schema"""
    
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
    if data.get("vin_correction"):
        ET.SubElement(form_2290, "VINCorrectionInd").text = "X"
    if data.get("final_return"):
        ET.SubElement(form_2290, "FinalReturnInd").text = "X"
    
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
    
    # Balance due (after any credits)
    credits = float(data.get("tax_credits", 0.0))
    balance_due = max(0.0, total_tax - credits)
    ET.SubElement(form_2290, "BalanceDueAmt").text = f"{balance_due:.2f}"
    
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

    
    # ── Return Pretty XML ───────────────────────────────
    rough = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")
