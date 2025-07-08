"""
Safe printing utility for Windows terminal compatibility
"""
import sys

def safe_print(text):
    """Print text with fallback for Unicode issues on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Strip emojis and Unicode symbols, keep only ASCII
        safe_text = ''.join(char for char in text if ord(char) < 128)
        print(safe_text)

def safe_format_status(status, text):
    """Format status messages with safe Unicode handling"""
    try:
        if status == "success":
            return f"✅ {text}"
        elif status == "error":
            return f"❌ {text}"
        elif status == "info":
            return f"🔍 {text}"
        elif status == "report":
            return f"📄 {text}"
        else:
            return text
    except UnicodeEncodeError:
        # Fallback to ASCII symbols
        if status == "success":
            return f"[OK] {text}"
        elif status == "error":
            return f"[ERROR] {text}"
        elif status == "info":
            return f"[INFO] {text}"
        elif status == "report":
            return f"[REPORT] {text}"
        else:
            return text
