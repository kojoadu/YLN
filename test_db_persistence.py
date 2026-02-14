#!/usr/bin/env python
"""Test the persistent database functionality."""

from app.db import init_db, get_conn

print('Testing persistent database initialization...')
try:
    # Initialize database
    init_db()
    print('✅ Database initialized successfully')
    
    # Test if tables exist in first connection
    with get_conn() as conn:
        tables = conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
        print('Available tables after init:', [table[0] for table in tables])
    
    # Test if tables still exist in second connection (persistence test)
    with get_conn() as conn:
        tables = conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
        print('Available tables after second connection:', [table[0] for table in tables])
        
        # Check specifically for sessions table
        sessions_check = conn.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="sessions"').fetchone()
        if sessions_check:
            print('✅ Sessions table exists and persists')
        else:
            print('❌ Sessions table missing')
            
except Exception as e:
    print('❌ Error during initialization:', e)
    import traceback
    traceback.print_exc()