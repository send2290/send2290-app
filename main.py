import sys
import os
# Add the current directory to path for backend imports
sys.path.insert(0, os.path.dirname(__file__))

from backend.xml_builder import build_2290_xml

xml_data = build_2290_xml()

with open("form2290.xml", "wb") as f:
    f.write(xml_data)

print("✅ form2290.xml has been generated successfully.")
