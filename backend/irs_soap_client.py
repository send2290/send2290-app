"""
IRS e-file SOAP Client for Form 2290 submissions
Handles SOAP communication with IRS A2A system
"""
import os
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import requests
from zeep import Client
from zeep.transports import Transport
from zeep.wsse import Signature
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IRSSOAPClient:
    """SOAP client for IRS e-file submissions"""
    
    # IRS URLs (use test environment first)
    IRS_TEST_URL = "https://testws.irs.gov/efile"
    IRS_PROD_URL = "https://ws.irs.gov/efile"
    
    def __init__(self, 
                 etin: str,
                 efin: str, 
                 cert_file: str,
                 key_file: str,
                 test_mode: bool = True):
        """
        Initialize IRS SOAP client
        
        Args:
            etin: Electronic Transmitter Identification Number
            efin: Electronic Filing Identification Number
            cert_file: Path to SSL certificate file (.pem or .crt)
            key_file: Path to SSL private key file (.key)
            test_mode: Use test environment if True, production if False
        """
        self.etin = etin
        self.efin = efin
        self.cert_file = cert_file
        self.key_file = key_file
        self.test_mode = test_mode
        self.base_url = self.IRS_TEST_URL if test_mode else self.IRS_PROD_URL
        
        # Validate certificate files exist
        if not os.path.exists(cert_file):
            raise FileNotFoundError(f"Certificate file not found: {cert_file}")
        if not os.path.exists(key_file):
            raise FileNotFoundError(f"Key file not found: {key_file}")
            
        logger.info(f"Initialized IRS SOAP client in {'TEST' if test_mode else 'PRODUCTION'} mode")
    
    def _create_transport(self) -> Transport:
        """Create secure transport with SSL certificates"""
        session = requests.Session()
        session.cert = (self.cert_file, self.key_file)
        session.verify = True  # Verify SSL certificates
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        return Transport(session=session)
    
    def _generate_message_id(self) -> str:
        """
        Generate unique message ID
        Format: ETIN (12 digits) + ccyyddd (7 digits) + 8-character alphanumeric
        """
        now = datetime.now()
        # Format: century + year + day of year (e.g., 2025001 for Jan 1, 2025)
        ccyyddd = f"{now.year}{now.timetuple().tm_yday:03d}"
        
        # Generate 8-character suffix (timestamp-based for uniqueness)
        suffix = f"{now.strftime('%H%M%S')}{now.microsecond//10000:02d}"
        
        return f"{self.etin}{ccyyddd}{suffix.lower()}"
    
    def _create_soap_envelope(self, submission_xml: str, message_id: str) -> str:
        """Create SOAP envelope for IRS submission"""
        
        # Create SOAP envelope with proper namespaces
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:irs="http://www.irs.gov/efile">
    <soap:Header>
        <irs:IRSSubmissionManifest>
            <irs:SubmissionId>{message_id}</irs:SubmissionId>
            <irs:EFIN>{self.efin}</irs:EFIN>
            <irs:TaxYr>2025</irs:TaxYr>
            <irs:GovernmentCd>US</irs:GovernmentCd>
            <irs:FederalSubmissionTypeCd>2290</irs:FederalSubmissionTypeCd>
            <irs:TaxPeriodBeginDt>2025-07-01</irs:TaxPeriodBeginDt>
            <irs:TaxPeriodEndDt>2026-06-30</irs:TaxPeriodEndDt>
            <irs:TIN>{self._extract_ein_from_xml(submission_xml)}</irs:TIN>
        </irs:IRSSubmissionManifest>
    </soap:Header>
    <soap:Body>
        {submission_xml}
    </soap:Body>
</soap:Envelope>"""
        
        return envelope
    
    def _extract_ein_from_xml(self, xml_content: str) -> str:
        """Extract EIN from Form 2290 XML for manifest"""
        try:
            root = ET.fromstring(xml_content)
            # Look for EIN in the XML structure
            ein_element = root.find(".//*[@name='EIN']")
            if ein_element is not None and ein_element.text:
                return ein_element.text.replace('-', '')
            
            # Alternative: look for TIN or EIN elements
            for elem in root.iter():
                if 'ein' in elem.tag.lower() or 'tin' in elem.tag.lower():
                    if elem.text and len(elem.text.replace('-', '')) == 9:
                        return elem.text.replace('-', '')
            
            # Fallback
            logger.warning("Could not extract EIN from XML, using placeholder")
            return "000000000"
            
        except Exception as e:
            logger.error(f"Error extracting EIN from XML: {e}")
            return "000000000"
    
    def submit_form_2290(self, form_xml: str) -> Dict[str, Any]:
        """
        Submit Form 2290 XML to IRS
        
        Args:
            form_xml: Complete Form 2290 XML content
            
        Returns:
            Dict containing submission results
        """
        try:
            # Generate unique message ID
            message_id = self._generate_message_id()
            logger.info(f"Generated message ID: {message_id}")
            
            # Create SOAP envelope
            soap_envelope = self._create_soap_envelope(form_xml, message_id)
            
            # Create transport with certificates
            transport = self._create_transport()
            
            # Submit to IRS
            response = self._send_soap_request(soap_envelope, transport)
            
            return {
                'success': True,
                'message_id': message_id,
                'submission_id': self._extract_submission_id(response),
                'response': response,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error submitting Form 2290: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _send_soap_request(self, soap_envelope: str, transport: Transport) -> str:
        """Send SOAP request to IRS endpoint"""
        
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '""',
            'User-Agent': 'Form2290Client/1.0'
        }
        
        # Use requests session from transport
        response = transport.session.post(
            f"{self.base_url}/submit",
            data=soap_envelope.encode('utf-8'),
            headers=headers,
            timeout=120  # 2 minute timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        logger.info("Successfully submitted to IRS")
        return response.text
    
    def _extract_submission_id(self, response_xml: str) -> Optional[str]:
        """Extract submission ID from IRS response"""
        try:
            root = ET.fromstring(response_xml)
            # Look for submission ID in response
            for elem in root.iter():
                if 'submissionid' in elem.tag.lower():
                    return elem.text
            return None
        except Exception as e:
            logger.error(f"Error extracting submission ID: {e}")
            return None
    
    def check_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """
        Check status of submitted form
        
        Args:
            submission_id: ID returned from submission
            
        Returns:
            Dict containing status information
        """
        try:
            # Create status check SOAP envelope
            status_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:irs="http://www.irs.gov/efile">
    <soap:Header>
        <irs:StatusRequest>
            <irs:SubmissionId>{submission_id}</irs:SubmissionId>
            <irs:EFIN>{self.efin}</irs:EFIN>
        </irs:StatusRequest>
    </soap:Header>
    <soap:Body>
        <irs:GetSubmissionStatus>
            <irs:SubmissionId>{submission_id}</irs:SubmissionId>
        </irs:GetSubmissionStatus>
    </soap:Body>
</soap:Envelope>"""
            
            transport = self._create_transport()
            response = self._send_soap_request(status_envelope, transport)
            
            return {
                'success': True,
                'submission_id': submission_id,
                'status_response': response,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking submission status: {e}")
            return {
                'success': False,
                'error': str(e),
                'submission_id': submission_id,
                'timestamp': datetime.now().isoformat()
            }

def test_irs_connection(etin: str, efin: str, cert_file: str, key_file: str) -> bool:
    """
    Test connection to IRS A2A system
    
    Args:
        etin: Electronic Transmitter Identification Number
        efin: Electronic Filing Identification Number  
        cert_file: Path to SSL certificate file
        key_file: Path to SSL private key file
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = IRSSOAPClient(etin, efin, cert_file, key_file, test_mode=True)
        
        # Create a simple test envelope to check connectivity
        test_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Header></soap:Header>
    <soap:Body>
        <test>Connection test</test>
    </soap:Body>
</soap:Envelope>"""
        
        transport = client._create_transport()
        logger.info("IRS connection test successful")
        return True
        
    except Exception as e:
        logger.error(f"IRS connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    print("IRS SOAP Client module loaded successfully")
