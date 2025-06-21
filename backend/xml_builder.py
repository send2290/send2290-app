from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

def build_2290_xml(data):
    """
    Build the IRS Form 2290 XML from the provided data dict,
    including a <PaymentMethod> section for EFTPS or Card.
    """
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

    # Root
    filer = Element('IRS2290Filer')

    # ReturnHeader
    hdr = SubElement(filer, 'ReturnHeader')
    SubElement(hdr, 'BusinessName').text    = str(data.get('business_name', ''))
    SubElement(hdr, 'EIN').text             = str(data.get('ein', ''))
    SubElement(hdr, 'Address').text         = str(data.get('address', ''))
    city = data.get('city', '')
    state = data.get('state', '')
    zipc = data.get('zip', '')
    SubElement(hdr, 'CityStateZip').text   = f"{city}, {state}, {zipc}"
    SubElement(hdr, 'TaxYear').text         = str(data.get('tax_year', ''))
    SubElement(hdr, 'UsedOnDate').text      = str(data.get('used_on_july', ''))
    SubElement(hdr, 'AddressChange').text   = str(data.get('address_change', False)).lower()
    SubElement(hdr, 'AmendedReturn').text   = str(data.get('amended_return', False)).lower()
    SubElement(hdr, 'VINCorrection').text   = str(data.get('vin_correction', False)).lower()
    SubElement(hdr, 'FinalReturn').text     = str(data.get('final_return', False)).lower()

    # Vehicles
    vehicles_el = SubElement(filer, 'Vehicles')
    for v in data.get('vehicles', []):
        ve = SubElement(vehicles_el, 'Vehicle')
        SubElement(ve, 'VIN').text            = str(v.get('vin', ''))
        SubElement(ve, 'Category').text       = str(v.get('category', ''))
        SubElement(ve, 'UsedMonth').text      = str(v.get('used_month', ''))
        SubElement(ve, 'IsLogging').text      = str(v.get('is_logging', False)).lower()
        SubElement(ve, 'IsSuspended').text    = str(v.get('is_suspended', False)).lower()
        SubElement(ve, 'IsAgricultural').text = str(v.get('is_agricultural', False)).lower()

        # Tax calculation
        is_susp = v.get('is_suspended', False)
        is_agri = v.get('is_agricultural', False)
        # If UsedMonth is passed as "1" or actually an int, this will cast safely:
        mon = int(v.get('used_month', 7))
        rate = logging_rates[v['category']] if v.get('is_logging') else full_rates[v['category']]
        if is_susp or is_agri:
            tax = 0.0
        elif mon == 7:
            tax = rate
        else:
            months_left = 13 - mon
            if months_left < 0:
                months_left += 12
            tax = round((rate * months_left) / 12, 2)

        SubElement(ve, 'TaxAmount').text = f"{tax:.2f}"

    # Signature
    sig = SubElement(filer, 'Signature')
    SubElement(sig, 'SignerName').text    = str(data.get('signature', ''))
    SubElement(sig, 'PrintedName').text   = str(data.get('printed_name', ''))
    SubElement(sig, 'SignatureDate').text = str(data.get('signature_date', ''))

    # PaymentMethod
    pm = SubElement(filer, 'PaymentMethod')
    if data.get('payEFTPS'):
        SubElement(pm, 'Method').text         = 'EFTPS'
        SubElement(pm, 'RoutingNumber').text  = str(data.get('eftps_routing', ''))
        SubElement(pm, 'AccountNumber').text  = str(data.get('eftps_account', ''))
    elif data.get('payCard'):
        SubElement(pm, 'Method').text         = 'Card'
        SubElement(pm, 'CardholderName').text = str(data.get('card_holder', ''))
        SubElement(pm, 'CardNumber').text     = str(data.get('card_number', ''))
        SubElement(pm, 'Expiration').text     = str(data.get('card_exp', ''))
        SubElement(pm, 'CVV').text            = str(data.get('card_cvv', ''))

    # Pretty print
    rough = tostring(filer, 'utf-8')
    dom   = parseString(rough)
    return dom.toprettyxml(indent='  ')
