"""Position tuner API routes"""
import json
import os
import datetime
import io
from flask import Blueprint, request, jsonify, make_response
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from config import Config
from utils.form_positions import load_form_positions, save_form_positions, get_fields_for_page
from utils.calculations import calculate_vehicle_statistics, add_dynamic_vin_fields
from services.audit_service import audit_logger

position_bp = Blueprint('positions', __name__)

# Global variable for form positions (will be loaded on startup)
FORM_POSITIONS = {}

def init_form_positions():
    """Initialize form positions on startup"""
    global FORM_POSITIONS
    FORM_POSITIONS = load_form_positions()
    print(f"✅ Blueprint FORM_POSITIONS loaded: {len(FORM_POSITIONS)} fields")

# Initialize positions when module is imported
init_form_positions()

@position_bp.route('', methods=['GET'])
def get_positions():
    """Get current form field positions"""
    try:
        return jsonify(FORM_POSITIONS)
    except Exception as e:
        audit_logger.error(f"get_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@position_bp.route('', methods=['POST'])
def update_positions():
    """Update form field positions"""
    global FORM_POSITIONS
    try:
        positions = request.get_json()
        if not positions:
            return jsonify({"error": "No position data provided"}), 400
        
        if save_form_positions(positions):
            FORM_POSITIONS = positions
            audit_logger.info("Positions updated and reloaded successfully")
            return jsonify({"message": "Positions updated and reloaded successfully"})
        else:
            return jsonify({"error": "Failed to save positions"}), 500
    except Exception as e:
        audit_logger.error(f"update_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@position_bp.route('/reload', methods=['POST'])
def reload_positions():
    """Reload form field positions from file"""
    global FORM_POSITIONS
    try:
        FORM_POSITIONS = load_form_positions()
        audit_logger.info("Positions reloaded successfully")
        return jsonify({"message": "Positions reloaded successfully", "positions": FORM_POSITIONS})
    except Exception as e:
        audit_logger.error(f"reload_positions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@position_bp.route('/update-offset', methods=['POST'])
def update_position_offset():
    """Update PDF offset values for a specific field"""
    try:
        data = request.get_json()
        field_name = data.get('field_name')
        x_offset = data.get('x_offset', 0)
        y_offset = data.get('y_offset', 0)
        
        if not field_name:
            return jsonify({"error": "field_name is required"}), 400
        
        if field_name not in FORM_POSITIONS:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        # Update offset values
        FORM_POSITIONS[field_name]["pdf_x_offset"] = int(x_offset)
        FORM_POSITIONS[field_name]["pdf_y_offset"] = int(y_offset)
        
        # Save updated positions
        if save_form_positions(FORM_POSITIONS):
            return jsonify({
                "success": True,
                "message": f"Updated PDF offsets for {field_name}",
                "field": field_name,
                "pdf_x_offset": x_offset,
                "pdf_y_offset": y_offset,
                "final_pdf_x": FORM_POSITIONS[field_name]["x"] + x_offset,
                "final_pdf_y": FORM_POSITIONS[field_name]["y"] + y_offset
            })
        else:
            return jsonify({"error": "Failed to save position updates"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@position_bp.route('/get-field-info/<field_name>', methods=['GET'])
def get_field_info(field_name):
    """Get detailed information about a specific field including offsets"""
    try:
        if field_name not in FORM_POSITIONS:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        field_data = FORM_POSITIONS[field_name]
        return jsonify({
            "field_name": field_name,
            "live_position": {
                "x": field_data["x"],
                "y": field_data["y"]
            },
            "pdf_offsets": {
                "x_offset": field_data.get("pdf_x_offset", 0),
                "y_offset": field_data.get("pdf_y_offset", 0)
            },
            "final_pdf_position": {
                "x": field_data["x"] + field_data.get("pdf_x_offset", 0),
                "y": field_data["y"] + field_data.get("pdf_y_offset", 0)
            },
            "font": field_data["font"],
            "size": field_data["size"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@position_bp.route('/reset-offset/<field_name>', methods=['POST'])
def reset_field_offset(field_name):
    """Reset PDF offsets for a specific field to zero"""
    try:
        if field_name not in FORM_POSITIONS:
            return jsonify({"error": f"Field '{field_name}' not found"}), 404
        
        # Reset offsets to zero
        FORM_POSITIONS[field_name]["pdf_x_offset"] = 0
        FORM_POSITIONS[field_name]["pdf_y_offset"] = 0
        
        # Save updated positions
        if save_form_positions(FORM_POSITIONS):
            return jsonify({
                "success": True,
                "message": f"Reset PDF offsets for {field_name}",
                "field": field_name,
                "pdf_x_offset": 0,
                "pdf_y_offset": 0
            })
        else:
            return jsonify({"error": "Failed to save position updates"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@position_bp.route('/test-pdf', methods=['POST'])
def test_pdf_with_offsets():
    """Generate a test PDF with sample data using current offset settings for all pages"""
    print("=== TEST PDF GENERATION STARTED ===")
    try:
        # Sample test data with comprehensive field coverage (from original backup)
        test_data = {
            "business_name": "TEST COMPANY LLC",
            "address": "123 Test Street",
            "city": "Test City",
            "state": "TX",
            "zip": "12345",
            "ein": "123456789",
            "tax_year": "2025",
            "used_on_july": "202507",
            "address_change": True,
            "vin_correction": True,  # Changed to True to show this checkbox
            "amended_return": True,  # Changed to True to show this checkbox
            "final_return": True,   # Changed to True to show this checkbox
            "has_disposals": True,   # Added this field
            "consent_to_disclose": True,  # Added this field
            "preparer_self_employed": True,  # Added this field
            "payEFTPS": True,  # Added this field
            "payCard": True,  # Changed to True to show this checkbox
            
            # Officer information
            "officer_name": "John Smith",
            "officer_title": "President",
            "printed_name": "John Smith",
            "signature": "John Smith",
            "signature_date": "2025-07-05",
            "taxpayer_phone": "5551234567",

            # Preparer information
            "preparer_name": "Jane Preparer",
            "preparer_ptin": "P12345678",
            "date_prepared": "2025-07-05",
            "preparer_firm_name": "Tax Prep LLC",
            "preparer_firm_ein": "987654321",
            "preparer_firm_address": "456 Tax Street",
            "preparer_firm_citystatezip": "Tax City, TX 67890",
            "preparer_firm_phone": "5559876543",
            
            # Designee information
            "designee_name": "Bob Designee",
            "designee_phone": "5555551234",
            "designee_pin": "54321",
            
            # Explanation fields
            "reasonable_cause_explanation": "Test explanation for amended return filing.",
            
            # Page 2 fields - Count fields (vehicle counts by category)
            "count_a_logging": "5",
            "count_a_regular": "3",
            "count_b_logging": "2", 
            "count_b_regular": "7",
            "count_c_logging": "1",
            "count_c_regular": "4",
            "count_d_logging": "6",
            "count_d_regular": "2",
            "count_e_logging": "3",
            "count_e_regular": "8",
            "count_f_logging": "1",
            "count_f_regular": "5",
            "count_g_logging": "2",
            "count_g_regular": "3",
            "count_h_logging": "4",
            "count_h_regular": "1",
            "count_i_logging": "7",
            "count_i_regular": "2",
            "count_j_logging": "1",
            "count_j_regular": "6",
            "count_k_logging": "3",
            "count_k_regular": "4",
            "count_l_logging": "2",
            "count_l_regular": "5",
            "count_m_logging": "1",
            "count_m_regular": "3",
            "count_n_logging": "4",
            "count_n_regular": "2",
            "count_o_logging": "1",
            "count_o_regular": "7",
            "count_p_logging": "2",
            "count_p_regular": "1",
            "count_q_logging": "3",
            "count_q_regular": "2",
            "count_r_logging": "1",
            "count_r_regular": "4",
            "count_s_logging": "2",
            "count_s_regular": "3",
            "count_t_logging": "1",
            "count_t_regular": "2",
            "count_u_logging": "3",
            "count_u_regular": "1",
            "count_v_logging": "2",
            "count_v_regular": "4",
            "count_w_suspended_logging": "1",
            "count_w_suspended_non_logging": "2",
            
            # Amount fields (tax amounts by category)
            "amount_a": "1250.00",
            "amount_b": "875.00",
            "amount_c": "650.00",
            "amount_d": "1100.00",
            "amount_e": "950.00",
            "amount_f": "750.00",
            "amount_g": "825.00",
            "amount_h": "425.00",
            "amount_i": "1375.00",
            "amount_j": "625.00",
            "amount_k": "1050.00",
            "amount_l": "800.00",
            "amount_m": "500.00",
            "amount_n": "725.00",
            "amount_o": "1200.00",
            "amount_p": "350.00",
            "amount_q": "675.00",
            "amount_r": "925.00",
            "amount_s": "775.00",
            "amount_t": "525.00",
            "amount_u": "850.00",
            "amount_v": "1150.00",
            "amount_w_suspended": "275.00",
            
            # Tax partial fields (partial period tax calculations)
            "tax_partial_a_logging": "125.50",
            "tax_partial_a_regular": "87.25",
            "tax_partial_b_logging": "95.75",
            "tax_partial_b_regular": "142.00",
            "tax_partial_c_logging": "68.50",
            "tax_partial_c_regular": "110.25",
            "tax_partial_d_logging": "156.75",
            "tax_partial_d_regular": "73.50",
            "tax_partial_e_logging": "89.25",
            "tax_partial_e_regular": "167.00",
            "tax_partial_f_logging": "45.75",
            "tax_partial_f_regular": "98.50",
            "tax_partial_g_logging": "112.25",
            "tax_partial_g_regular": "76.75",
            "tax_partial_h_logging": "134.50",
            "tax_partial_h_regular": "52.25",
            "tax_partial_i_logging": "178.75",
            "tax_partial_i_regular": "91.50",
            "tax_partial_j_logging": "64.25",
            "tax_partial_j_regular": "123.75",
            "tax_partial_k_logging": "145.50",
            "tax_partial_k_regular": "82.25",
            "tax_partial_l_logging": "67.75",
            "tax_partial_l_regular": "129.50",
            "tax_partial_m_logging": "58.25",
            "tax_partial_m_regular": "104.75",
            "tax_partial_n_logging": "116.50",
            "tax_partial_n_regular": "71.25",
            "tax_partial_o_logging": "93.75",
            "tax_partial_o_regular": "158.50",
            "tax_partial_p_logging": "79.25",
            "tax_partial_p_regular": "42.75",
            "tax_partial_q_logging": "127.50",
            "tax_partial_q_regular": "85.25",
            "tax_partial_r_logging": "61.75",
            "tax_partial_r_regular": "139.50",
            "tax_partial_s_logging": "103.25",
            "tax_partial_s_regular": "74.75",
            "tax_partial_t_logging": "88.50",
            "tax_partial_t_regular": "151.25",
            "tax_partial_u_logging": "96.75",
            "tax_partial_u_regular": "69.50",
            "tax_partial_v_logging": "121.25",
            "tax_partial_v_regular": "84.75",
            
            # Part I Tax Summary fields - Now using frontend calculated values
            "line2_tax": "15750.50", 
            "line3_increase": "0.00",
            "line4_total": "15750.50",
            "line5_credits": "250.00",
            "line6_balance": "15500.50",
            "total_logging_vehicles": "55",
            "total_regular_vehicles": "72",
            
            "vehicles": [
                {
                    "vin": "1HGBH41JXMN109186",
                    "category": "A",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "2HGBH41JXMN109187",
                    "category": "W",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": True
                },
                {
                    "vin": "3HGBH41JXMN109188",
                    "category": "W",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": True,
                    "is_agricultural": False
                },
                {
                    "vin": "4HGBH41JXMN109189",
                    "category": "B",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                },
                {
                    "vin": "5HGBH41JXMN109190",
                    "category": "C",
                    "used_month": "202507",
                    "is_logging": False,
                    "is_suspended": False,
                    "is_agricultural": False
                }
            ]
        }
        
        # Calculate vehicle statistics and add to test data
        vehicle_stats = calculate_vehicle_statistics(test_data.get("vehicles", []))
        test_data.update(vehicle_stats)
        
        # Add comprehensive category count and amount fields for testing
        weight_categories = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']
        for cat in weight_categories:
            cat_lower = cat.lower()
            # Add test count data
            regular_count = len([v for v in test_data["vehicles"] if v.get("category") == cat and not v.get("is_logging", False)])
            logging_count = len([v for v in test_data["vehicles"] if v.get("category") == cat and v.get("is_logging", False)])
            
            test_data[f"count_{cat_lower}_regular"] = str(regular_count)
            test_data[f"count_{cat_lower}_logging"] = str(logging_count)
            
            # Add test amount data (using sample tax amounts)
            if regular_count > 0:
                regular_amount = regular_count * 100.00  # Sample $100 per vehicle
                test_data[f"amount_{cat_lower}_regular"] = f"{regular_amount:.2f}"
                test_data[f"tax_partial_{cat_lower}_regular"] = "100.00"
            
            if logging_count > 0:
                logging_amount = logging_count * 75.00  # Sample $75 per logging vehicle
                test_data[f"amount_{cat_lower}_logging"] = f"{logging_amount:.2f}"
                test_data[f"tax_partial_{cat_lower}_logging"] = "75.00"
            
            # Total amount for category
            total_amount = (regular_count * 100.00) + (logging_count * 75.00)
            if total_amount > 0:
                test_data[f"amount_{cat_lower}"] = f"{total_amount:.2f}"
        
        # Add suspended vehicle counts
        test_data["count_w_suspended_non_logging"] = str(len([v for v in test_data["vehicles"] if v.get("category") == "W" and not v.get("is_logging", False)]))
        test_data["count_w_suspended_logging"] = str(len([v for v in test_data["vehicles"] if v.get("category") == "W" and v.get("is_logging", False)]))
        
        # Add dynamic VIN fields
        add_dynamic_vin_fields(test_data, test_data.get("vehicles", []))
        
        # Load template
        template_path = os.path.join(os.path.dirname(__file__), "..", Config.TEMPLATE_PDF_FILE)
        if not os.path.exists(template_path):
            return jsonify({"error": "Template not found"}), 500
            
        template = PdfReader(open(template_path, "rb"), strict=False)
        writer = PdfWriter()
        
        # Process each page
        for page_num in range(1, len(template.pages) + 1):
            # Get fields for this page
            fields_on_page = []
            for field_name, field_data in FORM_POSITIONS.items():
                # Skip special field types that don't have pages array
                if "x" not in field_data or "y" not in field_data:
                    continue
                    
                # Handle both old single page format and new pages array format
                field_pages = []
                if "pages" in field_data and isinstance(field_data["pages"], list):
                    if field_data["pages"]:  # If pages array is not empty
                        field_pages = field_data["pages"]
                    else:  # If pages array is empty, default to page 1
                        field_pages = [1]
                elif "page" in field_data:
                    field_pages = [field_data["page"]]
                else:
                    field_pages = [1]  # Default to page 1
                
                if page_num in field_pages:
                    fields_on_page.append(field_name)
            
            # Create overlay for this page
            overlay_page = _create_test_page_overlay(page_num, test_data, vehicle_stats.get('vehicles_by_month', {}), fields_on_page)
            
            # Merge with template page
            template_page = template.pages[page_num - 1]
            if overlay_page:
                template_page.merge_page(overlay_page)
            
            writer.add_page(template_page)
        
        # Create response
        buffer = io.BytesIO()
        writer.write(buffer)
        pdf_data = buffer.getvalue()
        buffer.close()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="offset_test_{timestamp}.pdf"'
        response.headers['Content-Length'] = len(pdf_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        print(f"Error generating test PDF: {str(e)}")
        return jsonify({"error": f"Failed to generate test PDF: {str(e)}"}), 500


def _create_test_page_overlay(page_num, test_data, month_vehicles, fields_on_page):
    """Create overlay with comprehensive field rendering (matches original logic)"""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    for field_name in fields_on_page:
        field_data = FORM_POSITIONS[field_name]
        
        # Skip fields that don't have x,y coordinates (special field types)
        if "x" not in field_data or "y" not in field_data:
            print(f"Skipping special field type: {field_name}")
            continue
        
        # Get position for this specific page (handle page-specific positions)
        pos_x = field_data["x"]
        pos_y = field_data["y"] 
        x_positions = field_data.get("x_positions")
        
        # Check for page-specific position overrides
        if "pagePositions" in field_data and str(page_num) in field_data["pagePositions"]:
            page_override = field_data["pagePositions"][str(page_num)]
            if "x" in page_override:
                pos_x = page_override["x"]
            if "y" in page_override:
                pos_y = page_override["y"]
            if "x_positions" in page_override:
                x_positions = page_override["x_positions"]
        
        # Apply offsets
        pdf_x_offset = field_data.get("pdf_x_offset", 0)
        pdf_y_offset = field_data.get("pdf_y_offset", 0)
        
        can.setFont(field_data["font"], field_data["size"])
        
        # Render based on field type - COMPLETE ORIGINAL LOGIC
        if field_name == "tax_year":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("tax_year", "2025"))
            
        elif field_name == "business_name":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("business_name", ""))
            
        elif field_name == "address":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("address", ""))
            
        elif field_name == "city_state_zip":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            city = test_data.get("city", "")
            state = test_data.get("state", "")
            zip_code = test_data.get("zip", "")
            city_state_zip = f"{city}, {state} {zip_code}"
            can.drawString(final_x, final_y, city_state_zip)
            
        elif field_name == "ein_digits" and x_positions:
            ein = test_data.get("ein", "").replace("-", "")
            for i, digit in enumerate(ein):
                if i < len(x_positions):
                    final_x = x_positions[i] + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, digit)
        
        elif field_name.startswith("vin_") and not field_name.endswith("_category") and x_positions:
            # Handle VIN fields with character-by-character spacing
            vin_value = test_data.get(field_name, "")
            print(f"🖊️ Rendering VIN field '{field_name}' = '{vin_value}' on page {page_num}")
            for i, char in enumerate(vin_value):
                if i < len(x_positions):
                    final_x = x_positions[i] + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, char)
        
        # Address fields
        elif field_name == "address_line2":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("address_line2", ""))
            
        elif field_name == "business_name_line2":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("business_name_line2", ""))
            
        elif field_name == "city":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("city", ""))
            
        elif field_name == "state":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("state", ""))
            
        elif field_name == "zip":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("zip", ""))
        
        # Amendment fields
        elif field_name == "amended_month":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("amended_month", ""))
            
        elif field_name == "reasonable_cause_explanation":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("reasonable_cause_explanation", ""))
            
        elif field_name == "vin_correction_explanation":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("vin_correction_explanation", ""))
            
        elif field_name == "special_conditions":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("special_conditions", ""))
        
        # Officer information
        elif field_name == "officer_name":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("officer_name", ""))
            
        elif field_name == "officer_title":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("officer_title", ""))
            
        elif field_name == "officer_ssn":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            ssn = test_data.get("officer_ssn", "")
            # Format SSN with dashes for display
            if len(ssn) == 9 and ssn.isdigit():
                ssn = f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
            can.drawString(final_x, final_y, ssn)
            
        elif field_name == "taxpayer_pin":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("taxpayer_pin", ""))
        
        # Preparer information
        elif field_name == "preparer_name":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_name", ""))
            
        elif field_name == "preparer_ptin":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_ptin", ""))
            
        elif field_name == "date_prepared":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("date_prepared", ""))
            
        elif field_name == "preparer_firm_name":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_firm_name", ""))
            
        elif field_name == "preparer_firm_ein":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                ein = test_data.get("preparer_firm_ein", "")
                # Format EIN with dash for display
                if len(ein) == 9 and ein.isdigit():
                    ein = f"{ein[:2]}-{ein[2:]}"
                can.drawString(final_x, final_y, ein)
            
        elif field_name == "preparer_firm_address":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_firm_address", ""))
            
        elif field_name == "preparer_firm_citystatezip":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_firm_citystatezip", ""))
            
        elif field_name == "preparer_firm_phone":
            if test_data.get("include_preparer", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("preparer_firm_phone", ""))
        
        # Third party designee information
        elif field_name == "designee_name":
            if test_data.get("consent_to_disclose", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("designee_name", ""))
            
        elif field_name == "designee_phone":
            if test_data.get("consent_to_disclose", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("designee_phone", ""))
            
        elif field_name == "designee_pin":
            if test_data.get("consent_to_disclose", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("designee_pin", ""))
        
        # Signature fields
        elif field_name == "signature":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("signature", ""))
            
        elif field_name == "printed_name":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("printed_name", ""))
            
        elif field_name == "signature_date":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("signature_date", ""))
        
        # Payment fields
        elif field_name == "eftps_routing":
            if test_data.get("payEFTPS", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("eftps_routing", ""))
            
        elif field_name == "eftps_account":
            if test_data.get("payEFTPS", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("eftps_account", ""))
            
        elif field_name == "account_type":
            if test_data.get("payEFTPS", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("account_type", ""))
            
        elif field_name == "payment_date":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("payment_date", ""))
            
        elif field_name == "taxpayer_phone":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("taxpayer_phone", ""))
        
        # Credit card payment fields
        elif field_name == "card_holder":
            if test_data.get("payCard", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("card_holder", ""))
            
        elif field_name == "card_number":
            if test_data.get("payCard", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                # Mask card number for security (show only last 4 digits)
                card_num = test_data.get("card_number", "")
                if len(card_num) > 4:
                    masked = "*" * (len(card_num) - 4) + card_num[-4:]
                    can.drawString(final_x, final_y, masked)
                else:
                    can.drawString(final_x, final_y, card_num)
            
        elif field_name == "card_exp":
            if test_data.get("payCard", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, test_data.get("card_exp", ""))
            
        elif field_name == "card_cvv":
            if test_data.get("payCard", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                # Don't render CVV for security
                can.drawString(final_x, final_y, "***")
        
        # Email field
        elif field_name == "email":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("email", ""))
            
        elif field_name == "used_on_july" and x_positions:
            used_on_july = test_data.get("used_on_july", "")
            print(f"🖊️ Rendering month field '{field_name}' = '{used_on_july}' on page {page_num}")
            for i, digit in enumerate(used_on_july):
                if i < len(x_positions):
                    final_x = x_positions[i] + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, digit)
            
        elif field_name == "used_on_july":
            # Fallback for when x_positions is not available
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            used_on_july = test_data.get("used_on_july", "")
            print(f"🖊️ Rendering month field '{field_name}' (fallback) = '{used_on_july}' on page {page_num}")
            can.drawString(final_x, final_y, used_on_july)
        
        # Additional checkbox fields
        elif field_name == "checkbox_has_disposals":
            if test_data.get("has_disposals", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
                
        elif field_name == "checkbox_preparer_self_employed":
            if test_data.get("include_preparer", False) and test_data.get("preparer_self_employed", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
                
        elif field_name == "checkbox_consent_to_disclose":
            if test_data.get("consent_to_disclose", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
                
        elif field_name == "checkbox_payEFTPS":
            if test_data.get("payEFTPS", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
                
        elif field_name == "checkbox_payCard":
            if test_data.get("payCard", False):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
        
        elif field_name.startswith("checkbox_"):
            # Handle checkboxes
            should_check = False
            if field_name == "checkbox_address_change":
                should_check = test_data.get("address_change", False)
            elif field_name == "checkbox_vin_correction":
                should_check = test_data.get("vin_correction", False)
            elif field_name == "checkbox_amended_return":
                should_check = test_data.get("amended_return", False)
            elif field_name == "checkbox_final_return":
                should_check = test_data.get("final_return", False)
            elif field_name == "checkbox_agricultural":
                # Check if any vehicle in this month is agricultural
                should_check = any(v.get("is_agricultural", False) for v in month_vehicles)
                print(f"🔍 Checking agricultural: {[v.get('is_agricultural', False) for v in month_vehicles]} -> {should_check}")
            elif field_name == "checkbox_non_agricultural":
                # Check if any vehicle in this month is non-agricultural with ≤5,000 miles
                should_check = any(v.get("mileage_5000_or_less", False) and not v.get("is_agricultural", False) 
                                 for v in month_vehicles)
                print(f"🔍 Checking non-agricultural ≤5k miles: {[(v.get('mileage_5000_or_less', False), v.get('is_agricultural', False)) for v in month_vehicles]} -> {should_check}")
            elif field_name == "checkbox_suspended":
                # Check if any vehicle in this month is suspended (category W)
                should_check = any(v.get("category", "") == "W" or v.get("is_suspended", False) 
                                 for v in month_vehicles)
                print(f"🔍 Checking suspended: {[(v.get('category', ''), v.get('is_suspended', False)) for v in month_vehicles]} -> {should_check}")
            
            if should_check:
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, "X")
                print(f"✅ Checking checkbox '{field_name}' on page {page_num} - condition met")
        
        # Vehicle statistics fields
        elif field_name == "total_reported_vehicles":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("total_reported_vehicles", ""))
            
        elif field_name == "total_suspended_vehicles":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("total_suspended_vehicles", ""))
            
        elif field_name == "total_taxable_vehicles":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            can.drawString(final_x, final_y, test_data.get("total_taxable_vehicles", ""))
        
        # Dynamic VIN fields (fallback when no x_positions available)
        elif field_name.startswith("vin_") and not field_name.endswith("_category") and not x_positions:
            # Handle VIN fields (vin_1, vin_2, etc.) - fallback when no x_positions available
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            vin_value = test_data.get(field_name, "")
            if vin_value:  # Only render if VIN exists
                can.drawString(final_x, final_y, vin_value)
                
        elif field_name.startswith("vin_") and field_name.endswith("_category"):
            # Handle VIN category fields (vin_1_category, vin_2_category, etc.)
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            category_value = test_data.get(field_name, "")
            print(f"🖊️ Rendering category field '{field_name}' = '{category_value}' on page {page_num}")
            if category_value:  # Only render if category exists
                can.drawString(final_x, final_y, category_value)
        
        elif field_name == "month_checkboxes":
            # Handle month checkboxes
            month_last_two = test_data.get("used_on_july", "07")[-2:] if test_data.get("used_on_july") else '07'
            if month_last_two in field_data:
                month_pos = field_data[month_last_two]
                final_x = month_pos["x"] + pdf_x_offset
                final_y = month_pos["y"] + pdf_y_offset
                can.drawString(final_x, final_y, "X")
        
        elif field_name == "vehicle_categories":
            # Handle vehicle category counts
            weight_counts = {}
            for vehicle in month_vehicles:
                category = vehicle.get('category', '')
                if category:
                    weight_counts[category] = weight_counts.get(category, 0) + 1
            
            # Draw vehicle counts in appropriate category boxes
            for category, count in weight_counts.items():
                if category in field_data:
                    cat_pos = field_data[category]
                    final_x = cat_pos["x"] + pdf_x_offset
                    final_y = cat_pos["y"] + pdf_y_offset
                    can.drawString(final_x, final_y, str(count))
        
        elif field_name == "tax_lines":
            # Handle Part I tax calculation lines using frontend-calculated values
            if "line2_tax" in field_data:
                line2_pos = field_data["line2_tax"]
                final_x = line2_pos["x"] + pdf_x_offset
                final_y = line2_pos["y"] + pdf_y_offset
                can.setFont(line2_pos["font"], line2_pos["size"])
                line2_value = test_data.get("line2_tax", "0.00")
                can.drawRightString(final_x, final_y, line2_value)
            
            if "line3_increase" in field_data:
                line3_pos = field_data["line3_increase"]
                final_x = line3_pos["x"] + pdf_x_offset
                final_y = line3_pos["y"] + pdf_y_offset
                can.setFont(line3_pos["font"], line3_pos["size"])
                line3_value = test_data.get("line3_increase", "0.00")
                can.drawRightString(final_x, final_y, line3_value)
            
            if "line4_total" in field_data:
                line4_pos = field_data["line4_total"]
                final_x = line4_pos["x"] + pdf_x_offset
                final_y = line4_pos["y"] + pdf_y_offset
                can.setFont(line4_pos["font"], line4_pos["size"])
                line4_value = test_data.get("line4_total", "0.00")
                can.drawRightString(final_x, final_y, line4_value)
            
            if "line5_credits" in field_data:
                line5_pos = field_data["line5_credits"]
                final_x = line5_pos["x"] + pdf_x_offset
                final_y = line5_pos["y"] + pdf_y_offset
                can.setFont(line5_pos["font"], line5_pos["size"])
                line5_value = test_data.get("line5_credits", "0.00")
                can.drawRightString(final_x, final_y, line5_value)
            
            if "line6_balance" in field_data:
                line6_pos = field_data["line6_balance"]
                final_x = line6_pos["x"] + pdf_x_offset
                final_y = line6_pos["y"] + pdf_y_offset
                can.setFont(line6_pos["font"], line6_pos["size"])
                line6_value = test_data.get("line6_balance", "0.00")
                can.drawRightString(final_x, final_y, line6_value)
        
        # Individual Part I fields - Handle standalone Part I line fields
        elif field_name.startswith("line") and "_" in field_name:
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            part_i_value = test_data.get(field_name, "0.00")
            print(f"📊 Rendering Part I field '{field_name}' = '{part_i_value}' on page {page_num}")
            can.drawRightString(final_x, final_y, part_i_value)
        
        # Category count fields - Handle count_a_regular, count_a_logging, etc.
        elif field_name.startswith("count_") and ("_regular" in field_name or "_logging" in field_name):
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            count_value = test_data.get(field_name, "0")
            # Only render if count > 0 to avoid cluttering the form
            if count_value and count_value != "0":
                print(f"📊 Rendering count field '{field_name}' = '{count_value}' on page {page_num}")
                can.drawString(final_x, final_y, count_value)
        
        # Category amount fields - Handle amount_a, amount_b, etc.
        elif field_name.startswith("amount_") and not field_name.endswith("_regular") and not field_name.endswith("_logging"):
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            amount_value = test_data.get(field_name, "0.00")
            # Only render if amount > 0 to avoid cluttering the form
            if amount_value and amount_value != "0.00":
                print(f"💰 Rendering amount field '{field_name}' = '{amount_value}' on page {page_num}")
                can.drawRightString(final_x, final_y, amount_value)
        
        # Partial-period tax fields - Handle tax_partial_a_regular, tax_partial_a_logging, etc.
        elif field_name.startswith("tax_partial_") and ("_regular" in field_name or "_logging" in field_name):
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            partial_tax_value = test_data.get(field_name, "0.00")
            # Only render if partial tax > 0 to avoid cluttering the form
            if partial_tax_value and partial_tax_value != "0.00":
                print(f"📊 Rendering partial tax field '{field_name}' = '{partial_tax_value}' on page {page_num}")
                can.drawRightString(final_x, final_y, partial_tax_value)
        
        # Category W suspended count fields
        elif field_name == "count_w_suspended_non_logging":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            count_value = test_data.get(field_name, "0")
            if count_value and count_value != "0":
                print(f"📊 Rendering category W non-logging count = '{count_value}' on page {page_num}")
                can.drawString(final_x, final_y, count_value)
        
        elif field_name == "count_w_suspended_logging":
            final_x = pos_x + pdf_x_offset
            final_y = pos_y + pdf_y_offset
            count_value = test_data.get(field_name, "0")
            if count_value and count_value != "0":
                print(f"📊 Rendering category W logging count = '{count_value}' on page {page_num}")
                can.drawString(final_x, final_y, count_value)
    
    can.save()
    packet.seek(0)
    
    packet.seek(0)
    
    overlay_page = PdfReader(packet).pages[0]
    return overlay_page
