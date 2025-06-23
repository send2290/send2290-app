import xml.etree.ElementTree as ET
from xml.dom import minidom

# Static tax tables (Table I and Logging Table II)
WEIGHT_RATES = {
    "A": 100.00, "B": 122.00, "C": 144.00, "D": 166.00, "E": 188.00, "F": 210.00,
    "G": 232.00, "H": 254.00, "I": 276.00, "J": 298.00, "K": 320.00, "L": 342.00,
    "M": 364.00, "N": 386.00, "O": 408.00, "P": 430.00, "Q": 452.00, "R": 474.00,
    "S": 496.00, "T": 518.00, "U": 540.00, "V": 550.00, "W":   0.00
}
LOGGING_RATES = {
    "A":  75.0,  "B":  91.5,  "C": 108.0, "D": 124.5, "E": 141.0, "F": 157.5,
    "G": 174.0, "H": 190.5, "I": 207.0, "J": 223.5, "K": 240.0, "L": 256.5,
    "M": 273.0, "N": 289.5, "O": 306.0, "P": 322.5, "Q": 339.0, "R": 355.5,
    "S": 372.0, "T": 388.5, "U": 405.0, "V": 412.5, "W":   0.0
}

def build_2290_xml(data: dict) -> str:
    """
    Build an IRS-compliant Form 2290 XML using the IRS XSL schemas.
    """
    root = ET.Element("IRS2290")

    # ── Filer (dynamic EIN to match ReturnHeader) ─────────
    filer = ET.SubElement(root, "Filer")
    ET.SubElement(filer, "DaytimePhoneNum").text = "3138506579"
    # Ensure EIN matches both places
    filer_ein = data.get("ein", "").replace("-", "").zfill(9)
    ET.SubElement(filer, "EIN").text = filer_ein
    ET.SubElement(filer, "AddressLine1Txt").text = "18673 Audette St"
    ET.SubElement(filer, "CityStateInfo").text   = "Dearborn, Michigan 48124"

    # ── ReturnHeader ───────────────────────────────────────
    hdr = ET.SubElement(filer, "ReturnHeader")
    ET.SubElement(hdr, "BusinessNameLine1Txt").text = data.get("business_name", "").strip()
    ET.SubElement(hdr, "BusinessNameLine2Txt").text = ""
    # Duplicate EIN here
    ET.SubElement(hdr, "EIN").text = filer_ein
    ET.SubElement(hdr, "Address").text = data.get("address", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    zipc = data.get("zip", "").strip()
    ET.SubElement(hdr, "CityStateZip").text = f"{city}, {state} {zipc}".strip().strip(",")
    ET.SubElement(hdr, "TaxYear").text    = str(data.get("tax_year", "")).strip()
    ET.SubElement(hdr, "UsedOnDate").text = str(data.get("used_on_july", "")).strip()
    # Optional flags
    if data.get("address_change"):   ET.SubElement(hdr, "AddressChangeInd")
    if data.get("amended_return"):   ET.SubElement(hdr, "AmendedReturnInd")
    if data.get("vin_correction"):   ET.SubElement(hdr, "VINCorrectionInd")
    if data.get("final_return"):     ET.SubElement(hdr, "FinalReturnInd")

    # ── Paid Preparer Person ──────────────────────────────
    if data.get("preparer_name"):
        prep = ET.SubElement(filer, "PreparerPersonGrp")
        ET.SubElement(prep, "PreparerPersonNm").text = data.get("preparer_name", "").strip()
        ET.SubElement(prep, "PTIN").text             = data.get("preparer_ptin", "").strip()
        ET.SubElement(prep, "DatePrepared").text     = data.get("date_prepared", "").strip()

    # ── Paid Preparer Firm ───────────────────────────────
    if data.get("preparer_firm_name"):
        firm = ET.SubElement(filer, "PreparerFirmGrp")
        ET.SubElement(firm, "BusinessNameLine1Txt").text = data.get("preparer_firm_name", "").strip()
        ET.SubElement(firm, "EIN").text                 = data.get("preparer_firm_ein", "").replace("-", "").zfill(9)
        ET.SubElement(firm, "AddressLine1Txt").text     = data.get("preparer_firm_address", "").strip()
        ET.SubElement(firm, "CityStateInfo").text      = data.get("preparer_firm_citystatezip", "").strip()
        ET.SubElement(firm, "DaytimePhoneNum").text     = data.get("preparer_firm_phone", "").strip()

    # ── Third-Party Designee / Consent ────────────────────
    if data.get("consent_to_disclose"):   ET.SubElement(filer, "ConsentToDiscloseYesInd")
    if data.get("designee_name"):
        des = ET.SubElement(filer, "ThirdPartyDesignee")
        ET.SubElement(des, "ThirdPartyDesigneeNm").text      = data.get("designee_name", "").strip()
        ET.SubElement(des, "ThirdPartyDesigneePhoneNum").text= data.get("designee_phone", "").strip()
        ET.SubElement(des, "ThirdPartyDesigneePIN").text     = data.get("designee_pin", "").strip()

    # ── Payment Indicator ────────────────────────────────
    if data.get("payEFTPS"):
        ET.SubElement(filer, "EFTPSPaymentInd")
    elif data.get("payCard"):
        ET.SubElement(filer, "CreditDebitCardPaymentInd")

    # ── Balance Due Amount (line 2) ───────────────────────
    total_tax = 0.0
    for v in data.get("vehicles", []):
        cat       = v.get("category", "").strip()
        used      = v.get("used_month", "").strip()
        logging   = bool(v.get("is_logging"))
        # prorate
        mon = int(used[-2:]) if used.isdigit() else 0
        months_left = 12 if mon >= 7 else (13 - mon if 1 <= mon <= 12 else 0)
        base = LOGGING_RATES[cat] if logging else WEIGHT_RATES[cat]
        amt = round(base * (months_left / 12), 2)
        total_tax += amt
    ET.SubElement(filer, "BalanceDueAmt").text = f"{total_tax:.2f}"

    # ── Schedule 1: Vehicles ──────────────────────────────
    sched1 = ET.SubElement(root, "IRS2290Schedule1")
    for v in data.get("vehicles", []):
        vin       = v.get("vin", "").strip()
        cat       = v.get("category", "").strip()
        used      = v.get("used_month", "").strip()
        logging   = bool(v.get("is_logging"))
        agr       = bool(v.get("is_agricultural"))
        suspended = bool(v.get("is_suspended"))
        mileage5k = bool(v.get("mileage_5000_or_less"))

        item_tag = "VehicleSuspendedTaxItem" if suspended else "VehicleReportTaxItem"
        item = ET.SubElement(sched1, item_tag)

        ET.SubElement(item, "VIN").text       = vin
        ET.SubElement(item, "Category").text  = cat
        ET.SubElement(item, "UsedMonth").text = used

        # prorated tax
        mon = int(used[-2:]) if used.isdigit() else 0
        months_left = 12 if mon >= 7 else (13 - mon if 1 <= mon <= 12 else 0)
        base = LOGGING_RATES[cat] if logging else WEIGHT_RATES[cat]
        amt = round(base * (months_left / 12), 2)
        ET.SubElement(item, "TaxAmount").text = f"{amt:.2f}"

        if logging:  ET.SubElement(item, "LoggingVehicleInd")
        if agr:      ET.SubElement(item, "AgricMileageUsed7500OrLessInd")
        if mileage5k:ET.SubElement(item, "Mileage5000OrLessInd")

    # ── pretty-print & return XML string ────────────────
    rough = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")
