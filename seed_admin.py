#!/usr/bin/env python
"""Seed the superadmin user."""

from app.db import seed_super_admin, get_user_by_email
from app.config import SUPER_ADMIN_EMAIL

print(f"Seeding superadmin with email: {SUPER_ADMIN_EMAIL}")
seed_super_admin()

user = get_user_by_email(SUPER_ADMIN_EMAIL)
if user:
    print(f"✓ Super admin seeded successfully")
    print(f"  Email: {user.get('email')}")
    print(f"  Role: {user.get('role')}")
    print(f"  Verified: {user.get('is_verified')}")
else:
    print("✗ Failed to seed super admin")
