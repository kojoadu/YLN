#!/usr/bin/env python
"""Check Google Sheets configuration for sheets-only mode."""

import os
from app.config import (
    USE_SQLITE, USE_SHEETS_ONLY, SHEETS_ENABLED, 
    SHEETS_SPREADSHEET_ID, SHEETS_CREDENTIALS_JSON, SHEETS_CREDENTIALS_PATH
)
from app.db import get_gspread_client, get_worksheet

def check_config():
    """Check the current database configuration."""
    print("🔧 Database Configuration Check")
    print("=" * 40)
    
    print(f"SQLite Enabled: {USE_SQLITE}")
    print(f"Sheets-Only Mode: {USE_SHEETS_ONLY}")
    print(f"Sheets Enabled: {SHEETS_ENABLED}")
    print()
    
    if USE_SHEETS_ONLY:
        print("✅ Running in Sheets-Only Mode")
        print("   - SQLite is disabled for data storage")
        print("   - Only in-memory database for session management")
        print("   - All user data stored in Google Sheets")
    else:
        print("ℹ️  Running in Hybrid Mode")
        print("   - SQLite is the primary database")
        print("   - Google Sheets used for sync/backup")
    
    print()

def check_sheets_connection():
    """Test Google Sheets connection."""
    print("📊 Google Sheets Connection Test")
    print("=" * 40)
    
    # Check credentials configuration
    if SHEETS_CREDENTIALS_JSON:
        print("✅ Credentials: JSON string provided")
    elif SHEETS_CREDENTIALS_PATH and os.path.exists(SHEETS_CREDENTIALS_PATH):
        print(f"✅ Credentials: File found at {SHEETS_CREDENTIALS_PATH}")
    else:
        print("❌ Credentials: No valid credentials found")
        print("   Set YLN_SHEETS_CREDENTIALS_JSON or YLN_SHEETS_CREDENTIALS_PATH")
        return False
    
    if SHEETS_SPREADSHEET_ID:
        print(f"✅ Spreadsheet ID: {SHEETS_SPREADSHEET_ID}")
    else:
        print("❌ Spreadsheet ID: Not configured")
        print("   Set YLN_SHEETS_SPREADSHEET_ID")
        return False
    
    # Test connection
    try:
        client = get_gspread_client()
        if client:
            print("✅ Connection: Successfully connected to Google Sheets API")
            
            # Test worksheet access
            worksheet = get_worksheet('users')
            if worksheet:
                print("✅ Users worksheet: Accessible")
                return True
            else:
                print("❌ Users worksheet: Could not access or create")
                return False
        else:
            print("❌ Connection: Failed to initialize Google Sheets client")
            return False
            
    except Exception as e:
        print(f"❌ Connection: Failed with error: {e}")
        return False

def main():
    """Run configuration and connection checks."""
    print("🔍 YLN Sheets-Only Mode Configuration Check")
    print("=" * 50)
    print()
    
    check_config()
    success = check_sheets_connection()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 All checks passed! Ready for Sheets-Only mode.")
    else:
        print("⚠️  Issues found. Please fix configuration before using Sheets-Only mode.")
        print()
        print("Required environment variables:")
        print("  - YLN_SHEETS_SPREADSHEET_ID: Your Google Sheets ID")
        print("  - YLN_SHEETS_CREDENTIALS_JSON: Service account JSON (as string)")
        print("  OR")
        print("  - YLN_SHEETS_CREDENTIALS_PATH: Path to service account JSON file")

if __name__ == "__main__":
    main()