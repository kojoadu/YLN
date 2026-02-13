#!/usr/bin/env python
"""Sync database to Google Sheets."""

from app.db import sync_all_to_sheets

print("Syncing database to Google Sheets...")
result = sync_all_to_sheets()

print("\nSync Results:")
print(f"  Users synced: {result.get('users_synced', 0)}")
print(f"  Sheets available: {result.get('sheets_available', False)}")

if result.get('success'):
    print("\n✓ Database synced successfully to Google Sheets")
else:
    print("\n✗ Sync completed with some issues (see details above)")
