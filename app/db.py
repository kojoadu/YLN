from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid

from app.config import (
    DB_PATH, Roles, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD,
    SHEETS_ENABLED, SHEETS_SPREADSHEET_ID, SHEETS_CREDENTIALS_JSON, SHEETS_CREDENTIALS_PATH
)
from app.security import hash_password

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Global gspread client (lazy initialized)
_gspread_client = None
_in_memory_fallback = False


def _connect() -> sqlite3.Connection:
    global _in_memory_fallback
    
    try:
        if _in_memory_fallback:
            # Use in-memory database if previous attempts failed
            conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
            print("Using in-memory database fallback")
        else:
            # Ensure the directory exists
            import os
            db_dir = os.path.dirname(DB_PATH)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"Created database directory: {db_dir}")
                except Exception as e:
                    print(f"Failed to create database directory {db_dir}: {e}")
            
            print(f"Attempting to connect to database: {DB_PATH}")
            conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
            print(f"Successfully connected to database: {DB_PATH}")
            
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        print(f"Attempted database path: {DB_PATH}")
        if not _in_memory_fallback:
            print("Falling back to in-memory database")
            _in_memory_fallback = True
            # Try again with in-memory database
            conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            print("Successfully connected to in-memory database")
            return conn
        else:
            raise


@contextmanager
def get_conn() -> sqlite3.Connection:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    global _in_memory_fallback
    
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                is_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verification_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                used INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mentors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                email TEXT NOT NULL,
                work_profile TEXT,
                bio TEXT,
                profile_pic TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mentees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                email TEXT NOT NULL,
                work_profile TEXT,
                profile_pic TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mentorships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL UNIQUE,
                mentee_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (mentor_id) REFERENCES mentors(id) ON DELETE CASCADE,
                FOREIGN KEY (mentee_id) REFERENCES mentees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pending_sheets_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                operation TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_retry_at TEXT NOT NULL,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    # Always seed super admin, especially important for in-memory database
    seed_super_admin()
    
    if _in_memory_fallback:
        print("⚠️ Database initialized in memory - data will not persist between sessions")


def get_gspread_client():
    """Get or create a gspread client using service account credentials."""
    global _gspread_client
    
    if not GSPREAD_AVAILABLE or not SHEETS_ENABLED:
        return None
        
    if _gspread_client is not None:
        return _gspread_client
        
    try:
        # Try to get credentials from Streamlit secrets first
        from app.config import get_gcp_service_account_info
        service_account_info = get_gcp_service_account_info()
        
        # Define the required scopes
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        if service_account_info:
            # Use service account info from Streamlit secrets
            credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        elif SHEETS_CREDENTIALS_JSON:
            # Use JSON string from environment
            import json
            creds_dict = json.loads(SHEETS_CREDENTIALS_JSON)
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        elif SHEETS_CREDENTIALS_PATH:
            # Use JSON file path
            credentials = Credentials.from_service_account_file(SHEETS_CREDENTIALS_PATH, scopes=scopes)
        else:
            return None
            
        _gspread_client = gspread.authorize(credentials)
        return _gspread_client
    except Exception as e:
        print(f"Failed to initialize gspread client: {e}")
        return None


def get_worksheet(tab_name: str):
    """Get a specific worksheet from the configured spreadsheet."""
    client = get_gspread_client()
    if not client or not SHEETS_SPREADSHEET_ID:
        return None
        
    try:
        spreadsheet = client.open_by_key(SHEETS_SPREADSHEET_ID)
        
        # Try to get existing worksheet or create it
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            # Create worksheet if it doesn't exist
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=20)
            
        return worksheet
    except Exception as e:
        print(f"Failed to get worksheet '{tab_name}': {e}")
        return None


def enqueue_sheets_write(entity_type: str, operation: str, payload: dict):
    """Enqueue a failed sheets write for retry later."""
    idempotency_key = str(uuid.uuid4())
    now = datetime.now().isoformat()
    next_retry = (datetime.now() + timedelta(seconds=60)).isoformat()
    
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO pending_sheets_writes 
            (entity_type, operation, payload_json, idempotency_key, next_retry_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entity_type, operation, json.dumps(payload), idempotency_key, next_retry, now, now))


def process_pending_sheets_writes():
    """Process pending sheets writes that are due for retry."""
    if not SHEETS_ENABLED:
        return
        
    now = datetime.now().isoformat()
    
    with get_conn() as conn:
        cursor = conn.execute("""
            SELECT id, entity_type, operation, payload_json, attempts
            FROM pending_sheets_writes 
            WHERE status = 'pending' AND next_retry_at <= ?
            ORDER BY created_at
            LIMIT 10
        """, (now,))
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row['payload_json'])
                
                # Mark as processing
                conn.execute("""
                    UPDATE pending_sheets_writes 
                    SET status = 'processing', updated_at = ?
                    WHERE id = ?
                """, (now, row['id']))
                
                # Try to write to sheets
                success = write_to_sheets(row['entity_type'], row['operation'], payload)
                
                if success:
                    # Mark as succeeded
                    conn.execute("""
                        DELETE FROM pending_sheets_writes WHERE id = ?
                    """, (row['id'],))
                else:
                    # Mark as failed, schedule retry
                    attempts = row['attempts'] + 1
                    if attempts >= 5:  # Max attempts
                        conn.execute("""
                            UPDATE pending_sheets_writes 
                            SET status = 'failed', attempts = ?, updated_at = ?
                            WHERE id = ?
                        """, (attempts, now, row['id']))
                    else:
                        next_retry = (datetime.now() + timedelta(seconds=60 * attempts)).isoformat()
                        conn.execute("""
                            UPDATE pending_sheets_writes 
                            SET status = 'pending', attempts = ?, next_retry_at = ?, updated_at = ?
                            WHERE id = ?
                        """, (attempts, next_retry, now, row['id']))
                        
            except Exception as e:
                # Mark as failed
                conn.execute("""
                    UPDATE pending_sheets_writes 
                    SET status = 'failed', last_error = ?, updated_at = ?
                    WHERE id = ?
                """, (str(e), now, row['id']))


def write_to_sheets(entity_type: str, operation: str, payload: dict) -> bool:
    """Write data to Google Sheets."""
    try:
        print(f"Writing to sheets - Type: {entity_type}, Operation: {operation}, Data: {list(payload.keys())}")
        
        worksheet = get_worksheet(entity_type)
        if not worksheet:
            print(f"Failed to get worksheet for {entity_type}")
            return False
            
        if operation == 'insert':
            # Get headers (first row)
            headers = worksheet.row_values(1)
            if not headers:
                # Create headers based on payload keys
                headers = list(payload.keys())
                worksheet.update('1:1', [headers])
                print(f"Created headers for {entity_type}: {headers}")
            
            # Append data row
            row_data = [payload.get(header, '') for header in headers]
            worksheet.append_row(row_data)
            print(f"Appended row to {entity_type}: {row_data}")
            
        elif operation == 'update':
            # Find row by id and update
            id_col = 1  # Assuming first column is ID
            id_value = payload.get('id')
            if not id_value:
                print(f"No ID found in payload for update operation")
                return False
                
            # Find the row
            try:
                cell = worksheet.find(str(id_value))
                if cell:
                    # Get headers and update row
                    headers = worksheet.row_values(1)
                    row_data = [payload.get(header, '') for header in headers]
                    worksheet.update(f'{cell.row}:{cell.row}', [row_data])
                    print(f"Updated row {cell.row} in {entity_type}")
                else:
                    # ID not found, treat as insert
                    print(f"ID {id_value} not found, treating as insert")
                    return write_to_sheets(entity_type, 'insert', payload)
            except Exception as e:
                # ID not found, treat as insert
                print(f"Error finding ID {id_value}, treating as insert: {e}")
                return write_to_sheets(entity_type, 'insert', payload)
                
        elif operation == 'delete':
            # Find row by id and delete
            id_value = payload.get('id')
            if not id_value:
                return False
                
            try:
                cell = worksheet.find(str(id_value))
                if cell:
                    worksheet.delete_rows(cell.row)
                    print(f"Deleted row {cell.row} from {entity_type}")
            except Exception as e:
                print(f"Error deleting from {entity_type}: {e}")
                
        return True
        
    except Exception as e:
        print(f"Failed to write to sheets ({entity_type}): {e}")
        return False


def delete_from_sheets(entity_type: str, record: dict) -> bool:
    """Delete a record from Google Sheets."""
    if not SHEETS_ENABLED:
        return False
    
    return write_to_sheets(entity_type, 'delete', record)


def dual_write(entity_type: str, operation: str, payload: dict):
    """Perform dual write to SQLite and Google Sheets."""
    # Always try to write to Sheets if enabled
    if SHEETS_ENABLED:
        success = write_to_sheets(entity_type, operation, payload)
        if not success:
            # Queue for retry
            enqueue_sheets_write(entity_type, operation, payload)


def seed_super_admin() -> None:
    if not SUPER_ADMIN_EMAIL or not SUPER_ADMIN_PASSWORD:
        return
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (SUPER_ADMIN_EMAIL,)
        ).fetchone()
        if existing:
            return
        conn.execute(
            """
            INSERT INTO users (email, password_hash, role, is_verified, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (
                SUPER_ADMIN_EMAIL,
                hash_password(SUPER_ADMIN_PASSWORD),
                Roles.ADMIN,
                _now(),
            ),
        )


def _now() -> str:
    return datetime.utcnow().isoformat()


def _expiry(hours: int = 24) -> str:
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _expiry_days(days: int = 7) -> str:
    return (datetime.utcnow() + timedelta(days=days)).isoformat()


def create_user(email: str, password_hash: str, role: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, role, is_verified, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (email.lower(), password_hash, role, _now()),
        )
        user_id = int(cur.lastrowid)
        
        # Dual write to sheets
        payload = {
            'id': user_id,
            'email': email.lower(),
            'password_hash': password_hash,
            'role': role,
            'is_verified': 0,
            'created_at': _now()
        }
        dual_write('users', 'insert', payload)
        
        return user_id


def read_from_sheets(entity_type: str, filters: dict = None) -> list:
    """Read data from Google Sheets with optional filters."""
    try:
        worksheet = get_worksheet(entity_type)
        if not worksheet:
            return []
            
        # Get all records
        records = worksheet.get_all_records()
        
        if not filters:
            return records
            
        # Apply filters
        filtered = []
        for record in records:
            match = True
            for key, value in filters.items():
                if str(record.get(key, '')).lower() != str(value).lower():
                    match = False
                    break
            if match:
                filtered.append(record)
                
        return filtered
        
    except Exception as e:
        print(f"Failed to read from sheets: {e}")
        return []


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    # Try sheets first
    if SHEETS_ENABLED:
        try:
            records = read_from_sheets('users', {'email': email.lower()})
            if records:
                user_record = records[0]  # Get first match
                
                # Handle column name inconsistency between sheets and SQLite
                # Ensure password_hash field exists, check for alternative names
                if 'password_hash' not in user_record and 'password' in user_record:
                    user_record['password_hash'] = user_record['password']
                
                # If we still don't have password_hash, fall back to SQLite
                if 'password_hash' not in user_record:
                    print(f"Password field missing from sheets for {email}, falling back to SQLite")
                else:
                    return user_record
        except Exception as e:
            print(f"Sheets read failed, falling back to SQLite: {e}")
    
    # Fallback to SQLite
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    # Try sheets first
    if SHEETS_ENABLED:
        try:
            records = read_from_sheets('users', {'id': str(user_id)})
            if records:
                return records[0]  # Return first match
        except Exception as e:
            print(f"Sheets read failed, falling back to SQLite: {e}")
    
    # Fallback to SQLite
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    """Get all users from the database."""
    # Get SQLite users first for reference
    sqlite_users = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, role, is_verified, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        sqlite_users = [dict(row) for row in rows]
    
    # If sheets enabled, try to get sheets data but validate against SQLite
    if SHEETS_ENABLED:
        try:
            sheets_users = read_from_sheets('users')
            if sheets_users:
                # Filter sheets users to only include those that exist in SQLite
                sqlite_ids = {user['id'] for user in sqlite_users}
                valid_sheets_users = [
                    user for user in sheets_users 
                    if user.get('id') in sqlite_ids
                ]
                print(f"Filtered {len(sheets_users)} sheets users to {len(valid_sheets_users)} valid users")
                return valid_sheets_users if valid_sheets_users else sqlite_users
        except Exception as e:
            print(f"Sheets read failed, falling back to SQLite: {e}")
    
    # Return SQLite data as fallback
    return sqlite_users


def set_user_verified(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
        conn.commit()
    
    # Dual write to sheets
    payload = {'id': user_id, 'is_verified': 1}
    dual_write('users', 'update', payload)


def update_user_role(user_id: int, role: str) -> bool:
    """Update user role."""
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
            )
            conn.commit()
        
        # Dual write to sheets
        payload = {'id': user_id, 'role': role}
        dual_write('users', 'update', payload)
        return True
    except Exception as e:
        print(f"Failed to update user role: {e}")
        return False


def toggle_user_verification(user_id: int) -> bool:
    """Toggle user verification status."""
    try:
        with get_conn() as conn:
            # Get current status
            current = conn.execute(
                "SELECT is_verified FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current:
                new_status = 0 if current[0] else 1
                conn.execute(
                    "UPDATE users SET is_verified = ? WHERE id = ?", (new_status, user_id)
                )
                conn.commit()
                
                # Dual write to sheets
                payload = {'id': user_id, 'is_verified': new_status}
                dual_write('users', 'update', payload)
                return True
        return False
    except Exception as e:
        print(f"Failed to toggle user verification: {e}")
        return False


def delete_user(user_id: int) -> bool:
    """Delete a user and all associated data."""
    try:
        # Get user info before deletion for sheets sync
        user_to_delete = None
        with get_conn() as conn:
            user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_row:
                user_to_delete = dict(user_row)
        
        if not user_to_delete:
            print(f"User {user_id} not found")
            return False
        
        with get_conn() as conn:
            # Delete associated data first
            conn.execute("DELETE FROM verification_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            
            # Delete mentee profile if exists
            mentee = conn.execute("SELECT id FROM mentees WHERE user_id = ?", (user_id,)).fetchone()
            if mentee:
                mentee_id = mentee[0]
                conn.execute("DELETE FROM mentorships WHERE mentee_id = ?", (mentee_id,))
                conn.execute("DELETE FROM sessions WHERE mentee_id = ?", (mentee_id,))
                conn.execute("DELETE FROM mentees WHERE user_id = ?", (user_id,))
            
            # Delete the user
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        
        # Sync deletion to Google Sheets
        if SHEETS_ENABLED:
            try:
                delete_from_sheets('users', user_to_delete)
                print(f"Successfully deleted user {user_id} from both SQLite and Sheets")
            except Exception as e:
                print(f"User deleted from SQLite but failed to sync deletion to Sheets: {e}")
        
        return True
    except Exception as e:
        print(f"Failed to delete user: {e}")
        return False


def create_verification_token(user_id: int, token: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO verification_tokens (user_id, token, expires_at, used, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (user_id, token, _expiry(), _now()),
        )


def use_verification_token(token: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM verification_tokens
            WHERE token = ? AND used = 0 AND expires_at >= ?
            """,
            (token, _now()),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE verification_tokens SET used = 1 WHERE id = ?", (row["id"],)
        )
        return int(row["user_id"])


def create_session(user_id: int, token: str, days: int = 7) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (user_id, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, token, _expiry_days(days), _now()),
        )


def get_session_user(token: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.*
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at >= ?
            """,
            (token, _now()),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def create_mentor(data: Dict[str, Any]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO mentors (
                first_name, last_name, phone, email, work_profile, bio, profile_pic,
                is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                data.get("first_name"),
                data.get("last_name"),
                data.get("phone"),
                data.get("email"),
                data.get("work_profile"),
                data.get("bio"),
                data.get("profile_pic"),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def list_available_mentors() -> list[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.*
            FROM mentors m
            WHERE m.is_active = 1
            AND m.id NOT IN (SELECT mentor_id FROM mentorships)
            ORDER BY m.last_name, m.first_name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_mentor(mentor_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM mentors WHERE id = ?", (mentor_id,)).fetchone()
        return dict(row) if row else None


def list_mentors() -> list[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM mentors
            ORDER BY last_name, first_name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_mentor(mentor_id: int, data: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE mentors
            SET first_name = ?, last_name = ?, phone = ?, email = ?,
                work_profile = ?, bio = ?, profile_pic = ?, is_active = ?
            WHERE id = ?
            """,
            (
                data.get("first_name"),
                data.get("last_name"),
                data.get("phone"),
                data.get("email"),
                data.get("work_profile"),
                data.get("bio"),
                data.get("profile_pic"),
                int(data.get("is_active", 1)),
                mentor_id,
            ),
        )


def delete_mentor(mentor_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mentors WHERE id = ?", (mentor_id,))


def create_or_update_mentee_profile(user_id: int, data: Dict[str, Any]) -> int:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM mentees WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE mentees
                SET first_name = ?, last_name = ?, phone = ?, email = ?,
                    work_profile = ?, profile_pic = ?
                WHERE user_id = ?
                """,
                (
                    data.get("first_name"),
                    data.get("last_name"),
                    data.get("phone"),
                    data.get("email"),
                    data.get("work_profile"),
                    data.get("profile_pic"),
                    user_id,
                ),
            )
            return int(existing["id"])
        cur = conn.execute(
            """
            INSERT INTO mentees (
                user_id, first_name, last_name, phone, email, work_profile,
                profile_pic, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.get("first_name"),
                data.get("last_name"),
                data.get("phone"),
                data.get("email"),
                data.get("work_profile"),
                data.get("profile_pic"),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def get_mentee_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM mentees WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_mentees() -> list[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM mentees
            ORDER BY last_name, first_name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_mentee(mentee_id: int, data: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE mentees
            SET first_name = ?, last_name = ?, phone = ?, email = ?,
                work_profile = ?, profile_pic = ?
            WHERE id = ?
            """,
            (
                data.get("first_name"),
                data.get("last_name"),
                data.get("phone"),
                data.get("email"),
                data.get("work_profile"),
                data.get("profile_pic"),
                mentee_id,
            ),
        )


def delete_mentee(mentee_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mentees WHERE id = ?", (mentee_id,))


def get_mentorship_by_mentee(mentee_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM mentorships WHERE mentee_id = ?", (mentee_id,)
        ).fetchone()
        return dict(row) if row else None


def list_mentor_pairs() -> list[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                m.id AS mentor_id,
                m.first_name AS mentor_first_name,
                m.last_name AS mentor_last_name,
                m.email AS mentor_email,
                me.id AS mentee_id,
                me.first_name AS mentee_first_name,
                me.last_name AS mentee_last_name,
                me.email AS mentee_email,
                ms.created_at AS paired_at
            FROM mentors m
            LEFT JOIN mentorships ms ON ms.mentor_id = m.id
            LEFT JOIN mentees me ON me.id = ms.mentee_id
            ORDER BY m.last_name, m.first_name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_mentorships() -> list[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, mentor_id, mentee_id, created_at
            FROM mentorships
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_mentorship(mentorship_id: int, mentor_id: int, mentee_id: int) -> tuple[bool, str]:
    with get_conn() as conn:
        try:
            conn.execute(
                """
                UPDATE mentorships
                SET mentor_id = ?, mentee_id = ?
                WHERE id = ?
                """,
                (mentor_id, mentee_id, mentorship_id),
            )
            return True, "Mentorship updated."
        except sqlite3.IntegrityError:
            return False, "Invalid assignment. Mentor or mentee already paired."


def delete_mentorship(mentorship_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mentorships WHERE id = ?", (mentorship_id,))


def assign_mentor(mentee_id: int, mentor_id: int) -> tuple[bool, str]:
    with get_conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO mentorships (mentor_id, mentee_id, created_at)
                VALUES (?, ?, ?)
                """,
                (mentor_id, mentee_id, _now()),
            )
            return True, "Mentor assigned."
        except sqlite3.IntegrityError:
            return False, "Mentor is no longer available or mentee already assigned."


def create_password_reset_token(user_id: int) -> str:
    """Create a new password reset token for a user."""
    import secrets
    import datetime
    
    token = secrets.token_urlsafe(32)
    # Token expires in 1 hour
    expires_at = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Mark any existing tokens as used
        cursor.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
            (user_id,)
        )
        
        # Create new token
        cursor.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, token, expires_at, datetime.datetime.now().isoformat())
        )
        conn.commit()
        return token
    finally:
        conn.close()


def get_password_reset_token(token: str) -> dict | None:
    """Get password reset token details if valid."""
    import datetime
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """SELECT prt.*, u.email 
               FROM password_reset_tokens prt 
               JOIN users u ON prt.user_id = u.id
               WHERE prt.token = ? AND prt.used = 0""",
            (token,)
        )
        result = cursor.fetchone()
        
        if not result:
            return None
            
        # Check if token is expired
        expires_at = datetime.datetime.fromisoformat(result[4])
        if datetime.datetime.now() > expires_at:
            return None
            
        return {
            'id': result[0],
            'user_id': result[1],
            'token': result[2],
            'expires_at': result[4],
            'email': result[6]
        }
    finally:
        conn.close()


def use_password_reset_token(token: str, new_password: str) -> bool:
    """Use password reset token to update user password."""
    import bcrypt
    
    token_data = get_password_reset_token(token)
    if not token_data:
        return False
        
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Update password
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hashed_password.decode('utf-8'), token_data['user_id'])
        )
        
        # Mark token as used
        cursor.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
            (token,)
        )
        
        conn.commit()
        
        # Try dual write to Google Sheets
        if GSPREAD_AVAILABLE and SHEETS_ENABLED:
            user = get_user_by_id(token_data['user_id'])
            if user:
                dual_write('users', 'update', {
                    'id': user['id'],
                    'email': user['email'],
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'password_hash': hashed_password.decode('utf-8'),
                    'is_verified': user['is_verified'],
                    'created_at': user['created_at']
                })
        
        return True
    finally:
        conn.close()


def sync_all_to_sheets() -> dict:
    """Sync all data from SQLite to Google Sheets."""
    if not GSPREAD_AVAILABLE or not SHEETS_ENABLED:
        return {'success': False, 'message': 'Google Sheets not available'}
    
    results = {
        'users': {'synced': 0, 'errors': 0},
        'mentors': {'synced': 0, 'errors': 0},
        'mentees': {'synced': 0, 'errors': 0},
        'mentorships': {'synced': 0, 'errors': 0},
        'sessions': {'synced': 0, 'errors': 0}
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Sync users
        cursor.execute("SELECT * FROM users")
        users = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for user in users:
            try:
                if write_to_sheets('users', 'insert', user):
                    results['users']['synced'] += 1
                else:
                    results['users']['errors'] += 1
            except Exception as e:
                print(f"Error syncing user {user.get('id')}: {e}")
                results['users']['errors'] += 1
        
        # Sync mentors
        cursor.execute("SELECT * FROM mentors")
        mentors = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for mentor in mentors:
            try:
                if write_to_sheets('mentors', 'insert', mentor):
                    results['mentors']['synced'] += 1
                else:
                    results['mentors']['errors'] += 1
            except Exception as e:
                print(f"Error syncing mentor {mentor.get('id')}: {e}")
                results['mentors']['errors'] += 1
        
        # Sync mentees
        cursor.execute("SELECT * FROM mentees")
        mentees = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for mentee in mentees:
            try:
                if write_to_sheets('mentees', 'insert', mentee):
                    results['mentees']['synced'] += 1
                else:
                    results['mentees']['errors'] += 1
            except Exception as e:
                print(f"Error syncing mentee {mentee.get('id')}: {e}")
                results['mentees']['errors'] += 1
        
        # Sync mentorships
        cursor.execute("SELECT * FROM mentorships")
        mentorships = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for mentorship in mentorships:
            try:
                if write_to_sheets('mentorships', 'insert', mentorship):
                    results['mentorships']['synced'] += 1
                else:
                    results['mentorships']['errors'] += 1
            except Exception as e:
                print(f"Error syncing mentorship {mentorship.get('id')}: {e}")
                results['mentorships']['errors'] += 1
        
        # Sync sessions
        cursor.execute("SELECT * FROM sessions")
        sessions = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for session in sessions:
            try:
                if write_to_sheets('sessions', 'insert', session):
                    results['sessions']['synced'] += 1
                else:
                    results['sessions']['errors'] += 1
            except Exception as e:
                print(f"Error syncing session {session.get('id')}: {e}")
                results['sessions']['errors'] += 1
        
        return {'success': True, 'results': results}
        
    except Exception as e:
        print(f"Error during sync: {e}")
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()


def clear_sheets_data(entity_type: str) -> bool:
    """Clear all data from a Google Sheets worksheet (except headers)."""
    try:
        worksheet = get_worksheet(entity_type)
        if not worksheet:
            return False
            
        # Get all values
        all_values = worksheet.get_all_values()
        if len(all_values) > 1:  # More than just headers
            # Clear all rows except header
            worksheet.delete_rows(2, len(all_values))
            
        return True
        
    except Exception as e:
        print(f"Error clearing sheets data for {entity_type}: {e}")
        return False
