from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString
import re

def build_2290_xml(data):
    """
    Build the IRS Form 2290 XML from the provided data dict,
    including vehicles, signature, and payment sections.
    Raises ValueError for validation issues.
    """
    # Helper to extract month integer from used_month field.
    def parse_used_month(used_month):
        """
        Accepts:
          - A string "YYYYMM" (e.g., "202507") -> returns 7
          - A string "MM" or "M" (e.g., "07" or "7") -> returns int
          - An int 1-12 -> returns as is
        Raises ValueError if cannot parse or out of range.
        """
        if used_month is None:
            raise ValueError("UsedMonth is missing")
        # If int already
        if isinstance(used_month, int):
            mon = used_month
        else:
            # It's a string: strip whitespace
            s = str(used_month).strip()
            # If matches YYYYMM
            if re.fullmatch(r"\d{6}", s):
                # last two digits
                mon = int(s[-2:])
            elif re.fullmatch(r"\d{1,2}", s):
                mon = int(s)
            else:
                raise ValueError(f"UsedMonth '{used_month}' is not in expected format")
        if not (1 <= mon <= 12):
            raise ValueError(f"UsedMonth '{used_month}' parsed to {mon}, which is out of 1-12 range")
        return mon

    # Full‐year tax rates (column a)
    full_rates = {
        'A': 100.00, 'B': 122.00, 'C': 144.00, 'D': 166.00, 'E': 188.00,
        'F': 210.00, 'G': 232.00, 'H': 254.00, 'I': 276.00, 'J': 298.00,
        'K': 320.00, 'L': 342.00, 'M': 364.00, 'N': 386.00, 'O': 408.00,
        'P': 430.00, 'Q': 452.00, 'R': 474.00, 'S': 496.00, 'T': 518.00,
        'U': 540.00, 'V': 550.00, 'W': 0.00
    }

    # Logging vehicle rates (column b)
    logging_rates = {
        'A': 75.00,  'B': 91.50,  'C': 108.00, 'D': 124.50, 'E': 141.00,
        'F': 157.50, 'G': 174.00, 'H': 190.50, 'I': 207.00, 'J': 223.50,
        'K': 240.00, 'L': 256.50, 'M': 273.00, 'N': 289.50, 'O': 306.00,
        'P': 322.50, 'Q': 339.00, 'R': 355.50, 'S': 372.00, 'T': 388.50,
        'U': 405.00, 'V': 412.50, 'W': 0.00
    }

    # Validate top-level required fields
    biz = data.get('business_name')
    ein = data.get('ein')
    if not biz or not str(biz).strip():
        raise ValueError("Business name is required")
    if not ein or not str(ein).strip():
        raise ValueError("EIN is required")
    # Optionally, ensure EIN is 9 digits:
    ein_str = str(ein).strip()
    if not re.fullmatch(r"\d{9}", ein_str):
        raise ValueError(f"EIN '{ein}' is not 9 digits")

    # Root element
    filer = Element('IRS2290Filer')

    # ReturnHeader
    hdr = SubElement(filer, 'ReturnHeader')
    SubElement(hdr, 'BusinessName').text    = biz.strip()
    SubElement(hdr, 'EIN').text             = ein_str
    SubElement(hdr, 'Address').text         = str(data.get('address', '') or '').strip()
    city = str(data.get('city', '') or '').strip()
    state = str(data.get('state', '') or '').strip()
    zipc = str(data.get('zip', '') or '').strip()
    SubElement(hdr, 'CityStateZip').text    = f"{city}, {state} {zipc}".strip().strip(',')
    SubElement(hdr, 'TaxYear').text         = str(data.get('tax_year', '') or '').strip()
    SubElement(hdr, 'UsedOnDate').text      = str(data.get('used_on_july', '') or '').strip()
    SubElement(hdr, 'AddressChange').text   = str(bool(data.get('address_change'))).lower()
    SubElement(hdr, 'AmendedReturn').text   = str(bool(data.get('amended_return'))).lower()
    SubElement(hdr, 'VINCorrection').text   = str(bool(data.get('vin_correction'))).lower()
    SubElement(hdr, 'FinalReturn').text     = str(bool(data.get('final_return'))).lower()

    # Vehicles
    vehicles_el = SubElement(filer, 'Vehicles')
    vehicles = data.get('vehicles')
    if vehicles is None or not isinstance(vehicles, list) or len(vehicles) == 0:
        # Depending on spec, it may require at least one vehicle
        raise ValueError("At least one vehicle entry is required")
    for idx, v in enumerate(vehicles, start=1):
        # Validate each vehicle dict
        if not isinstance(v, dict):
            raise ValueError(f"Vehicle #{idx} is not an object")
        vin = str(v.get('vin', '') or '').strip()
        if not vin:
            raise ValueError(f"Vehicle #{idx}: VIN is required")
        # VIN pattern: typically 17 alphanumeric, but you may relax
        if len(vin) != 17:
            # Warn or error; here we error
            raise ValueError(f"Vehicle #{idx}: VIN '{vin}' is not 17 characters")
        cat = str(v.get('category', '') or '').strip()
        if not cat:
            raise ValueError(f"Vehicle #{idx}: category (weight class) is required")
        if cat not in full_rates:
            raise ValueError(f"Vehicle #{idx}: category '{cat}' is not valid")
        used_month_raw = v.get('used_month')
        try:
            mon = parse_used_month(used_month_raw)
        except ValueError as ve:
            raise ValueError(f"Vehicle #{idx}: {ve}")
        is_logging = bool(v.get('is_logging'))
        is_suspended = bool(v.get('is_suspended'))
        is_agri = bool(v.get('is_agricultural'))
        # If Suspended (W), ensure category is 'W'?
        if cat == 'W' and not (is_suspended or is_agri):
            raise ValueError(f"Vehicle #{idx}: category 'W' requires is_suspended or is_agricultural flag")
        # If non-W but suspended/agri flags set, you might want to clear or error:
        # (depending on business logic; frontend likely already enforces mutual exclusion)

        # Create XML element
        ve = SubElement(vehicles_el, 'Vehicle')
        SubElement(ve, 'VIN').text            = vin
        SubElement(ve, 'Category').text       = cat
        # For UsedMonth XML: you may want full YYYYMM or just month; here we echo raw:
        SubElement(ve, 'UsedMonth').text      = str(used_month_raw or "").strip()
        SubElement(ve, 'IsLogging').text      = str(is_logging).lower()
        SubElement(ve, 'IsSuspended').text    = str(is_suspended).lower()
        SubElement(ve, 'IsAgricultural').text = str(is_agri).lower()

        # Tax calculation
        # Use correct rate dict:
        if cat not in full_rates:
            raise ValueError(f"Vehicle #{idx}: category '{cat}' has no rate")
        rate = logging_rates[cat] if is_logging else full_rates[cat]
        # Suspended or agricultural => zero tax
        if is_suspended or is_agri:
            tax = 0.0
        else:
            if mon == 7:
                tax = rate
            else:
                months_left = 13 - mon
                if months_left <= 0:
                    months_left += 12
                tax = round((rate * months_left) / 12, 2)
        SubElement(ve, 'TaxAmount').text = f"{tax:.2f}"

    # Signature
    # Signature fields might be optional or required. Validate if required.
    sig = SubElement(filer, 'Signature')
    signer = str(data.get('signature', '') or '').strip()
    printed = str(data.get('printed_name', '') or '').strip()
    sig_date = str(data.get('signature_date', '') or '').strip()
    # If signature fields are required:
    # if not signer or not printed or not sig_date:
    #     raise ValueError("Signature, PrintedName, SignatureDate are all required")
    SubElement(sig, 'SignerName').text    = signer
    SubElement(sig, 'PrintedName').text   = printed
    SubElement(sig, 'SignatureDate').text = sig_date

    # PaymentMethod
    pm = SubElement(filer, 'PaymentMethod')
    if data.get('payEFTPS'):
        # Validate routing/account presence
        routing = str(data.get('eftps_routing', '') or '').strip()
        account = str(data.get('eftps_account', '') or '').strip()
        if not routing or not account:
            raise ValueError("EFTPS selected but routing/account missing")
        SubElement(pm, 'Method').text         = 'EFTPS'
        SubElement(pm, 'RoutingNumber').text  = routing
        SubElement(pm, 'AccountNumber').text  = account
    elif data.get('payCard'):
        name = str(data.get('card_holder', '') or '').strip()
        num  = str(data.get('card_number', '') or '').strip()
        exp  = str(data.get('card_exp', '') or '').strip()
        cvv  = str(data.get('card_cvv', '') or '').strip()
        # Basic validation: non-empty
        if not (name and num and exp and cvv):
            raise ValueError("Card payment selected but fields missing")
        SubElement(pm, 'Method').text         = 'Card'
        SubElement(pm, 'CardholderName').text = name
        SubElement(pm, 'CardNumber').text     = num
        SubElement(pm, 'Expiration').text     = exp
        SubElement(pm, 'CVV').text            = cvv
    else:
        # No payment selected: depending on spec, may be allowed or error
        SubElement(pm, 'Method').text = 'None'

    # Pretty print
    rough = tostring(filer, 'utf-8')
    dom   = parseString(rough)
    # Optionally include XML declaration:
    pretty = dom.toprettyxml(indent='  ')
    # Optionally strip extraneous blank lines:
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines)
