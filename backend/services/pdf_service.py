"""PDF generation service for Form 2290"""
import os
import io
import datetime
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from config import Config
from utils.form_positions import load_form_positions, get_fields_for_page
from utils.calculations import group_vehicles_by_month, calculate_vehicle_statistics, add_dynamic_vin_fields
from services.s3_service import get_s3_client, upload_to_s3
from models import SessionLocal, Submission, FilingsDocument
from xml_builder import build_2290_xml
import json

class PDFGenerationService:
    def __init__(self):
        self.form_positions = load_form_positions()
        self.template_path = os.path.join(os.path.dirname(__file__), "..", Config.TEMPLATE_PDF_FILE)
        
    def generate_pdf_for_submission(self, data, user_uid):
        """Generate PDF(s) for form submission data"""
        # Validate input
        if not data.get("business_name") or not data.get("ein"):
            raise ValueError("Missing business_name or ein")
        
        if not os.path.exists(self.template_path):
            raise FileNotFoundError("PDF template not found")
        
        # Group vehicles by month
        vehicles_by_month = group_vehicles_by_month(data.get('vehicles', []))
        
        if not vehicles_by_month:
            raise ValueError("No vehicles found")
        
        created_files = []
        db = SessionLocal()
        s3 = get_s3_client()
        
        try:
            # Process each month separately
            for month, month_vehicles in vehicles_by_month.items():
                print(f"📅 Processing month {month} with {len(month_vehicles)} vehicles")
                
                # Create month-specific data
                month_data = self._prepare_month_data(data, month, month_vehicles)
                
                # Generate XML first
                xml_content = build_2290_xml(month_data)
                xml_key = f"{user_uid}/{month}/form2290.xml"
                
                # Upload XML to S3
                upload_success, error_msg = upload_to_s3(
                    xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content,
                    xml_key,
                    'application/xml'
                )
                
                if not upload_success:
                    print(f"Warning: XML upload failed for month {month}: {error_msg}")
                
                # Create submission record
                submission = Submission(
                    user_uid=user_uid,
                    month=month,
                    xml_s3_key=xml_key,
                    form_data=json.dumps(data)
                )
                db.add(submission)
                db.commit()
                db.refresh(submission)
                filing_id = submission.id
                
                # Add XML document record
                db.add(FilingsDocument(
                    filing_id=filing_id,
                    user_uid=user_uid,
                    document_type='xml',
                    s3_key=xml_key,
                    uploaded_at=datetime.datetime.utcnow()
                ))
                db.commit()
                
                # Generate PDF
                pdf_path = self._generate_pdf_for_month(month_data, month)
                
                # Upload PDF to S3
                pdf_key = f"{user_uid}/{month}/form2290.pdf"
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_upload_success, pdf_error = upload_to_s3(
                        pdf_file.read(),
                        pdf_key,
                        'application/pdf'
                    )
                
                if not pdf_upload_success:
                    print(f"Warning: PDF upload failed for month {month}: {pdf_error}")
                
                # Update submission with PDF key
                submission.pdf_s3_key = pdf_key
                db.commit()
                
                # Add PDF document record
                db.add(FilingsDocument(
                    filing_id=filing_id,
                    user_uid=user_uid,
                    document_type='pdf',
                    s3_key=pdf_key,
                    uploaded_at=datetime.datetime.utcnow()
                ))
                db.commit()
                
                created_files.append({
                    'month': month,
                    'filing_id': filing_id,
                    'vehicle_count': len(month_vehicles),
                    'pdf_path': pdf_path
                })
                
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
        
        return created_files
    
    def _prepare_month_data(self, data, month, month_vehicles):
        """Prepare form data for a specific month"""
        month_data = data.copy()
        month_data['vehicles'] = month_vehicles
        month_data['used_on_july'] = month
        
        # Calculate vehicle statistics
        vehicle_stats = calculate_vehicle_statistics(month_vehicles)
        month_data.update(vehicle_stats)
        
        # Add dynamic VIN fields
        add_dynamic_vin_fields(month_data, month_vehicles)
        
        # Calculate category counts and taxes (simplified version)
        weight_categories = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W']
        
        total_tax = 0
        for cat in weight_categories:
            cat_lower = cat.lower()
            
            # Count vehicles for this category
            regular_vehicles = [v for v in month_vehicles if v.get("category") == cat and not v.get("is_logging", False)]
            logging_vehicles = [v for v in month_vehicles if v.get("category") == cat and v.get("is_logging", False)]
            
            regular_count = len(regular_vehicles)
            logging_count = len(logging_vehicles)
            
            month_data[f"count_{cat_lower}_regular"] = str(regular_count)
            month_data[f"count_{cat_lower}_logging"] = str(logging_count)
            
            # Use frontend category data if available
            frontend_category_data = data.get('categoryData', {})
            if cat in frontend_category_data:
                frontend_cat_data = frontend_category_data[cat]
                
                # Determine tax type based on month
                month_num = int(month[-2:]) if month and len(month) >= 2 else 0
                is_annual_month = (month_num == 7)  # July = annual tax
                
                if is_annual_month:
                    regular_per_vehicle_rate = frontend_cat_data.get('regularAnnualTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                    logging_per_vehicle_rate = frontend_cat_data.get('loggingAnnualTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                else:
                    regular_per_vehicle_rate = frontend_cat_data.get('regularPartialTax', 0) / max(1, frontend_cat_data.get('regularCount', 1))
                    logging_per_vehicle_rate = frontend_cat_data.get('loggingPartialTax', 0) / max(1, frontend_cat_data.get('loggingCount', 1))
                
                regular_total_tax = regular_count * regular_per_vehicle_rate
                logging_total_tax = logging_count * logging_per_vehicle_rate
            else:
                regular_total_tax = 0
                logging_total_tax = 0
                regular_per_vehicle_rate = 0
                logging_per_vehicle_rate = 0
            
            total_category_tax = regular_total_tax + logging_total_tax
            total_tax += total_category_tax
            
            month_data[f"amount_{cat_lower}"] = f"{total_category_tax:.2f}"
            
            if regular_count > 0:
                month_data[f"tax_partial_{cat_lower}_regular"] = f"{regular_per_vehicle_rate:.2f}"
            if logging_count > 0:
                month_data[f"tax_partial_{cat_lower}_logging"] = f"{logging_per_vehicle_rate:.2f}"
        
        # Calculate disposal credits for this month
        month_disposal_credits = 0.0
        for vehicle in month_vehicles:
            if vehicle.get('disposal_credit'):
                try:
                    credit = float(vehicle['disposal_credit'])
                    month_disposal_credits += credit
                except (ValueError, TypeError):
                    pass
        
        # Part I calculations
        additional_tax = 0.00
        total_tax_with_additional = total_tax + additional_tax
        balance_due = max(0, total_tax_with_additional - month_disposal_credits)
        
        month_part_i = {
            'line2_tax': total_tax,
            'line3_increase': additional_tax,
            'line4_total': total_tax_with_additional,
            'line5_credits': month_disposal_credits,
            'line6_balance': balance_due
        }
        
        for field_name, field_value in month_part_i.items():
            month_data[field_name] = f"{field_value:.2f}"
        
        return month_data
    
    def _generate_pdf_for_month(self, month_data, month):
        """Generate PDF for a specific month"""
        template = PdfReader(open(self.template_path, "rb"), strict=False)
        writer = PdfWriter()
        
        # Process each page
        for page_num in range(1, len(template.pages) + 1):
            overlay = self._create_page_overlay(page_num, month_data, month)
            template_page = template.pages[page_num - 1]
            
            if overlay:
                template_page.merge_page(overlay)
            
            writer.add_page(template_page)
        
        # Save PDF
        out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"form2290_{month}.pdf")
        
        with open(out_path, "wb") as f:
            writer.write(f)
        
        return out_path
    
    def _create_page_overlay(self, page_num, month_data, month):
        """Create overlay for a specific page with form fields"""
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        
        # Get fields for this page
        fields_on_page = get_fields_for_page(self.form_positions, page_num)
        
        if not fields_on_page:
            can.save()
            packet.seek(0)
            return None
        
        print(f"Fields on page {page_num}: {fields_on_page}")
        
        # Get month vehicles for conditional logic
        month_vehicles = month_data.get("vehicles", [])
        
        # Render each field using the complete original logic
        for field_name in fields_on_page:
            field_data = self.form_positions[field_name]
            
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
                can.drawString(final_x, final_y, month_data.get("tax_year", "2025"))
                
            elif field_name == "business_name":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("business_name", ""))
                
            elif field_name == "address":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("address", ""))
                
            elif field_name == "city_state_zip":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                city = month_data.get("city", "")
                state = month_data.get("state", "")
                zip_code = month_data.get("zip", "")
                city_state_zip = f"{city}, {state} {zip_code}"
                can.drawString(final_x, final_y, city_state_zip)
                
            elif field_name == "ein_digits" and x_positions:
                ein = month_data.get("ein", "").replace("-", "")
                for i, digit in enumerate(ein):
                    if i < len(x_positions):
                        final_x = x_positions[i] + pdf_x_offset
                        final_y = pos_y + pdf_y_offset
                        can.drawString(final_x, final_y, digit)
            
            elif field_name.startswith("vin_") and not field_name.endswith("_category") and x_positions:
                # Handle VIN fields with character-by-character spacing
                vin_value = month_data.get(field_name, "")
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
                can.drawString(final_x, final_y, month_data.get("address_line2", ""))
                
            elif field_name == "business_name_line2":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("business_name_line2", ""))
                
            elif field_name == "city":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("city", ""))
                
            elif field_name == "state":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("state", ""))
                
            elif field_name == "zip":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("zip", ""))
            
            # Amendment fields
            elif field_name == "amended_month":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("amended_month", ""))
                
            elif field_name == "reasonable_cause_explanation":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("reasonable_cause_explanation", ""))
                
            elif field_name == "vin_correction_explanation":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("vin_correction_explanation", ""))
                
            elif field_name == "special_conditions":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("special_conditions", ""))
            
            # Officer information
            elif field_name == "officer_name":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("officer_name", ""))
                
            elif field_name == "officer_title":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("officer_title", ""))
                
            elif field_name == "officer_ssn":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                ssn = month_data.get("officer_ssn", "")
                # Format SSN with dashes for display
                if len(ssn) == 9 and ssn.isdigit():
                    ssn = f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
                can.drawString(final_x, final_y, ssn)
                
            elif field_name == "taxpayer_pin":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("taxpayer_pin", ""))
            
            # Preparer information
            elif field_name == "preparer_name":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_name", ""))
                
            elif field_name == "preparer_ptin":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_ptin", ""))
                
            elif field_name == "date_prepared":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("date_prepared", ""))
                
            elif field_name == "preparer_firm_name":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_firm_name", ""))
                
            elif field_name == "preparer_firm_ein":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    ein = month_data.get("preparer_firm_ein", "")
                    # Format EIN with dash for display
                    if len(ein) == 9 and ein.isdigit():
                        ein = f"{ein[:2]}-{ein[2:]}"
                    can.drawString(final_x, final_y, ein)
                
            elif field_name == "preparer_firm_address":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_firm_address", ""))
                
            elif field_name == "preparer_firm_citystatezip":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_firm_citystatezip", ""))
                
            elif field_name == "preparer_firm_phone":
                if month_data.get("include_preparer", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("preparer_firm_phone", ""))
            
            # Third party designee information
            elif field_name == "designee_name":
                if month_data.get("consent_to_disclose", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("designee_name", ""))
                
            elif field_name == "designee_phone":
                if month_data.get("consent_to_disclose", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("designee_phone", ""))
                
            elif field_name == "designee_pin":
                if month_data.get("consent_to_disclose", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("designee_pin", ""))
            
            # Signature fields
            elif field_name == "signature":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("signature", ""))
                
            elif field_name == "printed_name":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("printed_name", ""))
                
            elif field_name == "signature_date":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("signature_date", ""))
            
            # Payment fields
            elif field_name == "eftps_routing":
                if month_data.get("payEFTPS", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("eftps_routing", ""))
                
            elif field_name == "eftps_account":
                if month_data.get("payEFTPS", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("eftps_account", ""))
                
            elif field_name == "account_type":
                if month_data.get("payEFTPS", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("account_type", ""))
                
            elif field_name == "payment_date":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("payment_date", ""))
                
            elif field_name == "taxpayer_phone":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("taxpayer_phone", ""))
            
            # Credit card payment fields
            elif field_name == "card_holder":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("card_holder", ""))
                
            elif field_name == "card_number":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    # Mask card number for security (show only last 4 digits)
                    card_num = month_data.get("card_number", "")
                    if len(card_num) > 4:
                        masked = "*" * (len(card_num) - 4) + card_num[-4:]
                        can.drawString(final_x, final_y, masked)
                    else:
                        can.drawString(final_x, final_y, card_num)
                
            elif field_name == "card_exp":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("card_exp", ""))
                
            elif field_name == "card_cvv":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    # Don't render CVV for security
                    can.drawString(final_x, final_y, "***")
            
            # Email field
            elif field_name == "email":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("email", ""))
                
            elif field_name == "used_on_july" and x_positions:
                used_on_july = month_data.get("used_on_july", "")
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
                used_on_july = month_data.get("used_on_july", "")
                print(f"🖊️ Rendering month field '{field_name}' (fallback) = '{used_on_july}' on page {page_num}")
                can.drawString(final_x, final_y, used_on_july)
            
            # Additional checkbox fields
            elif field_name == "checkbox_has_disposals":
                if month_data.get("has_disposals", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, "X")
                    
            elif field_name == "checkbox_preparer_self_employed":
                if month_data.get("include_preparer", False) and month_data.get("preparer_self_employed", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, "X")
                    
            elif field_name == "checkbox_consent_to_disclose":
                if month_data.get("consent_to_disclose", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, "X")
                    
            elif field_name == "checkbox_payEFTPS":
                if month_data.get("payEFTPS", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, "X")
                    
            elif field_name == "checkbox_payCard":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, "X")
            
            elif field_name.startswith("checkbox_"):
                # Handle checkboxes
                should_check = False
                if field_name == "checkbox_address_change":
                    should_check = month_data.get("address_change", False)
                elif field_name == "checkbox_vin_correction":
                    should_check = month_data.get("vin_correction", False)
                elif field_name == "checkbox_amended_return":
                    should_check = month_data.get("amended_return", False)
                elif field_name == "checkbox_final_return":
                    should_check = month_data.get("final_return", False)
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
                can.drawString(final_x, final_y, month_data.get("total_reported_vehicles", ""))
                
            elif field_name == "total_suspended_vehicles":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("total_suspended_vehicles", ""))
                
            elif field_name == "total_taxable_vehicles":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("total_taxable_vehicles", ""))
            
            # Credit card payment fields
            elif field_name == "card_holder":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("card_holder", ""))
                
            elif field_name == "card_number":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    # Mask card number for security (show only last 4 digits)
                    card_num = month_data.get("card_number", "")
                    if len(card_num) > 4:
                        masked = "*" * (len(card_num) - 4) + card_num[-4:]
                        can.drawString(final_x, final_y, masked)
                    else:
                        can.drawString(final_x, final_y, card_num)
                
            elif field_name == "card_exp":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    can.drawString(final_x, final_y, month_data.get("card_exp", ""))
                
            elif field_name == "card_cvv":
                if month_data.get("payCard", False):
                    final_x = pos_x + pdf_x_offset
                    final_y = pos_y + pdf_y_offset
                    # Don't render CVV for security
                    can.drawString(final_x, final_y, "***")
            
            # Email field
            elif field_name == "email":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("email", ""))
                
            elif field_name == "used_on_july" and x_positions:
                used_on_july = month_data.get("used_on_july", "")
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
                used_on_july = month_data.get("used_on_july", "")
                print(f"🖊️ Rendering month field '{field_name}' (fallback) = '{used_on_july}' on page {page_num}")
                can.drawString(final_x, final_y, used_on_july)
            
            # Checkbox fields with conditional logic
            elif field_name.startswith("checkbox_"):
                should_check = False
                if field_name == "checkbox_address_change":
                    should_check = month_data.get("address_change", False)
                elif field_name == "checkbox_vin_correction":
                    should_check = month_data.get("vin_correction", False)
                elif field_name == "checkbox_amended_return":
                    should_check = month_data.get("amended_return", False)
                elif field_name == "checkbox_final_return":
                    should_check = month_data.get("final_return", False)
                elif field_name == "checkbox_has_disposals":
                    should_check = month_data.get("has_disposals", False)
                elif field_name == "checkbox_consent_to_disclose":
                    should_check = month_data.get("consent_to_disclose", False)
                elif field_name == "checkbox_preparer_self_employed":
                    should_check = month_data.get("include_preparer", False) and month_data.get("preparer_self_employed", False)
                elif field_name == "checkbox_payEFTPS":
                    should_check = month_data.get("payEFTPS", False)
                elif field_name == "checkbox_payCard":
                    should_check = month_data.get("payCard", False)
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
                can.drawString(final_x, final_y, month_data.get("total_reported_vehicles", ""))
                
            elif field_name == "total_suspended_vehicles":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("total_suspended_vehicles", ""))
                
            elif field_name == "total_taxable_vehicles":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                can.drawString(final_x, final_y, month_data.get("total_taxable_vehicles", ""))
            
            # Dynamic VIN fields (fallback when no x_positions)
            elif field_name.startswith("vin_") and not field_name.endswith("_category") and not x_positions:
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                vin_value = month_data.get(field_name, "")
                if vin_value:
                    can.drawString(final_x, final_y, vin_value)
                    
            elif field_name.startswith("vin_") and field_name.endswith("_category"):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                category_value = month_data.get(field_name, "")
                print(f"🖊️ Rendering category field '{field_name}' = '{category_value}' on page {page_num}")
                if category_value:
                    can.drawString(final_x, final_y, category_value)
            
            # Category count fields
            elif field_name.startswith("count_") and ("_regular" in field_name or "_logging" in field_name):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                count_value = month_data.get(field_name, "0")
                if count_value and count_value != "0":
                    print(f"📊 Rendering count field '{field_name}' = '{count_value}' on page {page_num}")
                    can.drawString(final_x, final_y, count_value)
            
            # Category amount fields
            elif field_name.startswith("amount_") and not field_name.endswith("_regular") and not field_name.endswith("_logging"):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                amount_value = month_data.get(field_name, "0.00")
                if amount_value and amount_value != "0.00":
                    print(f"💰 Rendering amount field '{field_name}' = '{amount_value}' on page {page_num}")
                    can.drawRightString(final_x, final_y, amount_value)
            
            # Partial-period tax fields
            elif field_name.startswith("tax_partial_") and ("_regular" in field_name or "_logging" in field_name):
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                partial_tax_value = month_data.get(field_name, "0.00")
                if partial_tax_value and partial_tax_value != "0.00":
                    print(f"📊 Rendering partial tax field '{field_name}' = '{partial_tax_value}' on page {page_num}")
                    can.drawRightString(final_x, final_y, partial_tax_value)
            
            # Part I tax line fields
            elif field_name.startswith("line") and "_" in field_name:
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                part_i_value = month_data.get(field_name, "0.00")
                print(f"📊 Rendering Part I field '{field_name}' = '{part_i_value}' on page {page_num}")
                can.drawRightString(final_x, final_y, part_i_value)
            
            # Category W suspended count fields
            elif field_name == "count_w_suspended_non_logging":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                count_value = month_data.get(field_name, "0")
                if count_value and count_value != "0":
                    print(f"📊 Rendering category W non-logging count = '{count_value}' on page {page_num}")
                    can.drawString(final_x, final_y, count_value)
            
            elif field_name == "count_w_suspended_logging":
                final_x = pos_x + pdf_x_offset
                final_y = pos_y + pdf_y_offset
                count_value = month_data.get(field_name, "0")
                if count_value and count_value != "0":
                    print(f"📊 Rendering category W logging count = '{count_value}' on page {page_num}")
                    can.drawString(final_x, final_y, count_value)
            
            # Complex field types from original implementation
            elif field_name == "month_checkboxes":
                # Handle month checkboxes
                month_last_two = month[-2:] if len(month) >= 2 else '07'
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
                    line2_value = month_data.get("line2_tax", "0.00")
                    can.drawRightString(final_x, final_y, line2_value)
                
                if "line3_increase" in field_data:
                    line3_pos = field_data["line3_increase"]
                    final_x = line3_pos["x"] + pdf_x_offset
                    final_y = line3_pos["y"] + pdf_y_offset
                    can.setFont(line3_pos["font"], line3_pos["size"])
                    line3_value = month_data.get("line3_increase", "0.00")
                    can.drawRightString(final_x, final_y, line3_value)
                
                if "line4_total" in field_data:
                    line4_pos = field_data["line4_total"]
                    final_x = line4_pos["x"] + pdf_x_offset
                    final_y = line4_pos["y"] + pdf_y_offset
                    can.setFont(line4_pos["font"], line4_pos["size"])
                    line4_value = month_data.get("line4_total", "0.00")
                    can.drawRightString(final_x, final_y, line4_value)
                
                if "line5_credits" in field_data:
                    line5_pos = field_data["line5_credits"]
                    final_x = line5_pos["x"] + pdf_x_offset
                    final_y = line5_pos["y"] + pdf_y_offset
                    can.setFont(line5_pos["font"], line5_pos["size"])
                    line5_value = month_data.get("line5_credits", "0.00")
                    can.drawRightString(final_x, final_y, line5_value)
                
                if "line6_balance" in field_data:
                    line6_pos = field_data["line6_balance"]
                    final_x = line6_pos["x"] + pdf_x_offset
                    final_y = line6_pos["y"] + pdf_y_offset
                    can.setFont(line6_pos["font"], line6_pos["size"])
                    line6_value = month_data.get("line6_balance", "0.00")
                    can.drawRightString(final_x, final_y, line6_value)
        
        can.save()
        packet.seek(0)
        
        overlay_page = PdfReader(packet).pages[0]
        return overlay_page
    
    def _should_check_checkbox(self, field_name, month_data):
        """Determine if a checkbox should be checked"""
        if field_name == "checkbox_address_change":
            return month_data.get("address_change", False)
        elif field_name == "checkbox_vin_correction":
            return month_data.get("vin_correction", False)
        elif field_name == "checkbox_amended_return":
            return month_data.get("amended_return", False)
        elif field_name == "checkbox_final_return":
            return month_data.get("final_return", False)
        elif field_name == "checkbox_has_disposals":
            return month_data.get("has_disposals", False)
        elif field_name == "checkbox_consent_to_disclose":
            return month_data.get("consent_to_disclose", False)
        elif field_name == "checkbox_payEFTPS":
            return month_data.get("payEFTPS", False)
        elif field_name == "checkbox_payCard":
            return month_data.get("payCard", False)
        elif field_name == "checkbox_agricultural":
            vehicles = month_data.get("vehicles", [])
            return any(v.get("is_agricultural", False) for v in vehicles)
        elif field_name == "checkbox_suspended":
            vehicles = month_data.get("vehicles", [])
            return any(v.get("category", "") == "W" or v.get("is_suspended", False) for v in vehicles)
        elif field_name == "checkbox_non_agricultural":
            vehicles = month_data.get("vehicles", [])
            return any(v.get("mileage_5000_or_less", False) and not v.get("is_agricultural", False) for v in vehicles)
        
        return False

    def generate_preview_pdf(self, data):
        """Generate a preview PDF without storing to database or S3"""
        # Validate input
        if not data.get("business_name") or not data.get("ein"):
            raise ValueError("Missing business_name or ein")
        
        if not os.path.exists(self.template_path):
            raise FileNotFoundError("PDF template not found")
        
        # For preview, use the primary month or default to July
        vehicles = data.get('vehicles', [])
        if not vehicles:
            raise ValueError("No vehicles found")
        
        # Group vehicles by month, but for preview just use the first month or July
        vehicles_by_month = group_vehicles_by_month(vehicles)
        
        if not vehicles_by_month:
            # Default to July if no specific month found
            preview_month = "2025-07"
            month_vehicles = vehicles
        else:
            # Use the first month available
            preview_month = list(vehicles_by_month.keys())[0]
            month_vehicles = vehicles_by_month[preview_month]
        
        print(f"📅 Generating preview for month {preview_month} with {len(month_vehicles)} vehicles")
        
        # Create month-specific data for preview
        month_data = self._prepare_month_data(data, preview_month, month_vehicles)
        
        # Generate PDF for preview
        preview_pdf_path = self._generate_preview_pdf_for_month(month_data, preview_month)
        
        return preview_pdf_path

    def generate_preview_pdfs_all_months(self, data):
        """Generate preview PDFs for all months found in the vehicle data"""
        # Validate input
        if not data.get("business_name") or not data.get("ein"):
            raise ValueError("Missing business_name or ein")
        
        if not os.path.exists(self.template_path):
            raise FileNotFoundError("PDF template not found")
        
        # Group vehicles by month
        vehicles_by_month = group_vehicles_by_month(data.get('vehicles', []))
        
        if not vehicles_by_month:
            raise ValueError("No vehicles found")
        
        created_previews = []
        
        print(f"📅 Generating previews for {len(vehicles_by_month)} month(s): {list(vehicles_by_month.keys())}")
        
        for month, month_vehicles in vehicles_by_month.items():
            print(f"📅 Processing preview for month {month} with {len(month_vehicles)} vehicles")
            
            # Create month-specific data
            month_data = self._prepare_month_data(data, month, month_vehicles)
            
            # Generate PDF for this month
            preview_pdf_path = self._generate_preview_pdf_for_month(month_data, month)
            
            created_previews.append({
                'month': month,
                'vehicle_count': len(month_vehicles),
                'pdf_path': preview_pdf_path
            })
        
        return created_previews

    def _generate_preview_pdf_for_month(self, month_data, month):
        """Generate preview PDF for a specific month (separate from main generation)"""
        template = PdfReader(open(self.template_path, "rb"), strict=False)
        writer = PdfWriter()
        
        # Process each page
        for page_num in range(1, len(template.pages) + 1):
            overlay = self._create_page_overlay(page_num, month_data, month)
            template_page = template.pages[page_num - 1]
            
            if overlay:
                template_page.merge_page(overlay)
            
            writer.add_page(template_page)
        
        # Save preview PDF to a different location
        out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"preview_form2290_{month}.pdf")
        
        with open(out_path, "wb") as f:
            writer.write(f)
        
        return out_path
