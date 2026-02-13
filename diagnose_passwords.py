#!/usr/bin/env python
"""Debug password handling and credentials."""

from app.db import get_user_by_email, list_users
from app.security import hash_password, verify_password
from app.config import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD

print("=== Password Handling Diagnostics ===\n")

# Check superadmin
print(f"Super Admin Credentials:")
print(f"  Email: {SUPER_ADMIN_EMAIL}")
print(f"  Password: {SUPER_ADMIN_PASSWORD}")

user = get_user_by_email(SUPER_ADMIN_EMAIL)
if user:
    print(f"\n✓ Super Admin found in database")
    stored_hash = user.get('password_hash', '')
    print(f"  Stored hash: {stored_hash[:30] if stored_hash else 'EMPTY'}...")
    print(f"  Hash length: {len(stored_hash) if stored_hash else 0}")
    
    # Test password verification
    if stored_hash:
        try:
            is_valid = verify_password(SUPER_ADMIN_PASSWORD, stored_hash)
            print(f"  Password verification: {'✓ VALID' if is_valid else '✗ INVALID'}")
        except Exception as e:
            print(f"  Password verification error: {e}")
    else:
        print(f"  ✗ No password hash stored!")
else:
    print(f"✗ Super Admin NOT found in database")

# List all users
print(f"\n=== All Users in Database ===")
users = list_users()
for user in users:
    email = user.get('email', 'N/A')
    pwhash = user.get('password_hash', '')
    verified = user.get('is_verified', False)
    print(f"\nUser: {email}")
    print(f"  Hash: {pwhash[:30] if pwhash else 'EMPTY'}...")
    print(f"  Verified: {verified}")
    print(f"  Fields: {list(user.keys())}")
