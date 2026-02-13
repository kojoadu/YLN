#!/usr/bin/env python
"""Debug login flow with sheets lookup."""

from app.db import get_user_by_email, read_from_sheets
from app.security import verify_password
from app.config import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD

print("=== Login Flow Debugging ===\n")

email = SUPER_ADMIN_EMAIL
password = SUPER_ADMIN_PASSWORD

print(f"Step 1: Getting user by email from sheets/db")
print(f"  Email: {email}")
user = get_user_by_email(email)

if user:
    print(f"\n✓ User found")
    print(f"  Fields returned: {list(user.keys())}")
    
    # Check password_hash field
    password_hash = user.get("password_hash")
    print(f"\nStep 2: Extract password_hash")
    print(f"  password_hash present: {bool(password_hash)}")
    print(f"  password_hash value: {password_hash[:30] if password_hash else 'EMPTY'}...")
    print(f"  password_hash type: {type(password_hash)}")
    
    # Try to verify
    print(f"\nStep 3: Verify password")
    if password_hash:
        try:
            is_valid = verify_password(password, password_hash)
            print(f"  Input password: {password}")
            print(f"  Stored hash: {password_hash[:30]}...")
            print(f"  Verification result: {'✓ VALID' if is_valid else '✗ INVALID'}")
        except Exception as e:
            print(f"  ✗ Verification error: {e}")
            print(f"  Hash type: {type(password_hash)}")
    else:
        print(f"  ✗ No password_hash to verify!")
else:
    print(f"✗ User not found")

# Also check what's in sheets directly
print(f"\n=== Direct Sheets Lookup ===")
sheets_records = read_from_sheets('users', {'email': email.lower()})
if sheets_records:
    print(f"Found {len(sheets_records)} record(s)")
    record = sheets_records[0]
    print(f"Sheets record fields: {list(record.keys())}")
    print(f"Sheets password_hash: {record.get('password_hash', 'MISSING')[:30] if record.get('password_hash') else 'EMPTY'}...")
else:
    print("No records found in sheets")
