"""Utility functions for form positions and PDF generation"""
import json
import os
from config import Config

def load_form_positions():
    """Load form field positions from JSON file"""
    try:
        positions_file = os.path.join(os.path.dirname(__file__), "..", Config.FORM_POSITIONS_FILE)
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                return json.load(f)
        else:
            print(f"Warning: {Config.FORM_POSITIONS_FILE} not found")
            return {}
    except Exception as e:
        print(f"Error loading form positions: {e}")
        return {}

def save_form_positions(positions):
    """Save form field positions to JSON file"""
    try:
        positions_file = os.path.join(os.path.dirname(__file__), "..", Config.FORM_POSITIONS_FILE)
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving form positions: {e}")
        return False

def get_fields_for_page(positions, page_num):
    """Get all fields that should appear on a specific page"""
    fields = []
    for field_name, field_data in positions.items():
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
            fields.append(field_name)
    
    return fields
