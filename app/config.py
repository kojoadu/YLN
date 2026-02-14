from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Try to import streamlit for secrets, fall back to env vars
try:
    import streamlit as st
    def get_config_value(key, default=""):
        try:
            return st.secrets.get(key, os.getenv(key, default))
        except:
            return os.getenv(key, default)
except ImportError:
    def get_config_value(key, default=""):
        return os.getenv(key, default)

BASE_DIR = Path(__file__).resolve().parent

# Create data directory - use temp dir for cloud deployment if needed
try:
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Test if we can write to this directory
    test_file = DATA_DIR / ".test"
    test_file.write_text("test")
    test_file.unlink()
except (PermissionError, OSError):
    # Fallback to temp directory for cloud deployments
    import tempfile
    DATA_DIR = Path(tempfile.gettempdir()) / "yln_data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = get_config_value("YLN_DB_PATH", "")
if not DB_PATH:
    DB_PATH = str(DATA_DIR / "yln.db")

SUPER_ADMIN_EMAIL = get_config_value("YLN_SUPER_ADMIN_EMAIL", "admin@yln.local")
SUPER_ADMIN_PASSWORD = get_config_value("YLN_SUPER_ADMIN_PASSWORD", "admin1234")

SMTP_HOST = get_config_value("YLN_SMTP_HOST", "")
SMTP_PORT = int(get_config_value("YLN_SMTP_PORT", "587"))
SMTP_USER = get_config_value("YLN_SMTP_USER", "")
SMTP_PASS = get_config_value("YLN_SMTP_PASS", "")
SMTP_FROM = get_config_value("YLN_SMTP_FROM", "noreply@yln.local")
smtp_tls_val = get_config_value("YLN_SMTP_TLS", "true")
SMTP_TLS = str(smtp_tls_val).lower() == "true"

# Debug SMTP configuration (don't log passwords)
print(f"SMTP Configuration loaded:")
print(f"  HOST: {SMTP_HOST}")
print(f"  PORT: {SMTP_PORT}")  
print(f"  USER: {SMTP_USER}")
print(f"  FROM: {SMTP_FROM}")
print(f"  TLS: {SMTP_TLS}")
print(f"  PASS: {'***' if SMTP_PASS else 'EMPTY'}")

# Database configuration
USE_SQLITE = False  # Disable SQLite
USE_SHEETS_ONLY = True  # Use Google Sheets as primary storage

# Google Sheets configuration
sheets_enabled_val = get_config_value("YLN_SHEETS_ENABLED", "true" if USE_SHEETS_ONLY else "false")
SHEETS_ENABLED = USE_SHEETS_ONLY or str(sheets_enabled_val).lower() == "true"
SHEETS_SPREADSHEET_ID = get_config_value("YLN_SHEETS_SPREADSHEET_ID", "")
SHEETS_CREDENTIALS_JSON = get_config_value("YLN_SHEETS_CREDENTIALS_JSON", "")
SHEETS_CREDENTIALS_PATH = get_config_value("YLN_SHEETS_CREDENTIALS_PATH", "")
SHEETS_RETRY_ATTEMPTS = int(get_config_value("YLN_SHEETS_RETRY_ATTEMPTS", "3"))
SHEETS_RETRY_DELAY = int(get_config_value("YLN_SHEETS_RETRY_DELAY", "1"))

# Helper function to get Google service account credentials from Streamlit secrets
def get_gcp_service_account_info():
    """Get Google service account credentials from Streamlit secrets."""
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
        return None
    except ImportError:
        return None
SHEETS_RETRY_DELAY = int(os.getenv("YLN_SHEETS_RETRY_DELAY", "60"))

APP_NAME = "Yello Ladies Network Mentorship"

@dataclass(frozen=True)
class Roles:
    ADMIN: str = "admin"
    MENTEE: str = "mentee"
