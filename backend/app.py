from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter

# Import xml_builder from same folder
# Ensure xml_builder.py is next to this file
from xml_builder import build_2290_xml

app = Flask(__name__)

# ----------------------
# CORS: allow dev origins. Adjust for production.
# Added explicit methods and headers to satisfy preflight POST
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://10.0.0.166:3000",
        "http://localhost:3001",
        "http://10.0.0.166:3001",
        # In production, add your real frontend domain, e.g.: https://your-production-frontend.com
    ]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
# ----------------------

# Helper: always resolve files relative to this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Send2290 API is up. Use POST /build-xml to generate XML, GET /download-xml or GET /download-pdf"
    }), 200

@app.route("/build-xml", methods=["POST", "OPTIONS"])
def generate_xml():
    # Handle preflight OPTIONS
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}
    # Optional: basic validation
    if not data.get("business_name") or not data.get("ein"):
        return jsonify({"error": "Missing business_name or ein"}), 400

    try:
        xml_data = build_2290_xml(data)
    except Exception as e:
        app.logger.error("Error in build_2290_xml: %s", e, exc_info=True)
        return jsonify({"error": f"Error building XML: {str(e)}"}), 500

    # Ensure xml_data is string
    if isinstance(xml_data, bytes):
        try:
            xml_data = xml_data.decode("utf-8")
        except Exception:
            xml_data = xml_data.decode(errors="ignore")

    xml_path = os.path.join(SCRIPT_DIR, "form2290.xml")
    try:
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_data)
    except Exception as e:
        app.logger.error("Failed to write XML file: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to write XML file: {str(e)}"}), 500

    # Store last form data for PDF generation
    app.config["last_form_data"] = data

    return jsonify({"message": "✅ XML generated", "xml": xml_data}), 200

@app.route("/download-xml", methods=["GET"])
def download_xml():
    xml_path = os.path.join(SCRIPT_DIR, "form2290.xml")
    if not os.path.exists(xml_path):
        return jsonify({"error": "XML not generated yet"}), 404
    # Optionally specify download_name
    return send_file(xml_path, mimetype="application/xml", as_attachment=True)

@app.route("/download-pdf", methods=["GET"])
def download_pdf():
    data = app.config.get("last_form_data")
    if not data:
        return jsonify({"error": "No form data submitted yet"}), 400

    template_path = os.path.join(SCRIPT_DIR, "f2290_template.pdf")
    if not os.path.exists(template_path):
        app.logger.error("Template not found at %s", template_path)
        return jsonify({"error": f"Template not found at {template_path}"}), 500

    try:
        template = PdfReader(open(template_path, "rb"), strict=False)
    except Exception as e:
        app.logger.error("Failed to read template PDF: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to read template PDF: {str(e)}"}), 500

    writer = PdfWriter()
    overlays = []

    # Build overlay pages
    for page_index in range(len(template.pages)):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        if page_index == 0:
            # Header fields
            can.setFont("Helvetica", 10)
            can.drawString(105, 715, data.get("business_name", ""))
            can.drawString(365, 715, data.get("ein", ""))
            can.drawString(500, 715, data.get("used_on_july", ""))
            can.drawString(105, 692, data.get("address", ""))
            city = data.get("city", "")
            state = data.get("state", "")
            zipcode = data.get("zip", "")
            city_state = f"{city}, {state} {zipcode}".strip()
            can.drawString(105, 674, city_state)
            # Checkboxes
            if data.get("address_change"):
                can.drawString(95, 652, "✔")
            if data.get("amended_return"):
                can.drawString(95, 634, "✔")
            if data.get("vin_correction"):
                can.drawString(355, 652, "✔")
            if data.get("final_return"):
                can.drawString(355, 634, "✔")
        else:
            vehicles = data.get("vehicles", [])
            if page_index == 1:
                start_y = 498
                x_vin, x_cat = (80, 250)
            else:
                start_y = 410
                x_vin, x_cat = (80, 320)
            spacing = 20
            for i, v in enumerate(vehicles[:24]):
                y = start_y - i * spacing
                can.setFont("Helvetica", 10)
                can.drawString(x_vin, y, v.get("vin", "")[:17])
                can.drawString(x_cat, y, v.get("category", ""))
                if v.get("is_agricultural"):
                    can.drawString(450, y, "✔")
                if v.get("is_suspended"):
                    can.drawString(470, y, "✔")
                if v.get("is_logging"):
                    can.drawString(430, y, "✔")

        can.save()
        packet.seek(0)
        try:
            overlay_page = PdfReader(packet).pages[0]
            overlays.append(overlay_page)
        except Exception as e:
            app.logger.error("Failed to create overlay for page %d: %s", page_index, e, exc_info=True)
            return jsonify({"error": f"Failed to create overlay for page {page_index}: {str(e)}"}), 500

    # Merge overlays onto template pages
    for idx, page in enumerate(template.pages):
        try:
            page.merge_page(overlays[idx])
        except Exception as e:
            app.logger.error("Failed to merge overlay page %d: %s", idx, e, exc_info=True)
            return jsonify({"error": f"Failed to merge overlay on page {idx}: {str(e)}"}), 500
        writer.add_page(page)

    # Write result PDF
    out_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "form2290_filled.pdf")
    try:
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
    except Exception as e:
        app.logger.error("Failed to write filled PDF: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to write filled PDF: {str(e)}"}), 500

    # Return the filled PDF
    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    # For local dev: listen on all interfaces so LAN IP can reach it
    app.run(host="0.0.0.0", port=5000, debug=True)
