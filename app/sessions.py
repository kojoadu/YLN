from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional, Dict, Any

from app import db


def create_session(user_id: int, hours: int = 1, days: int = None) -> str:
    """Create a session token with hour or day based expiry."""
    token = secrets.token_urlsafe(32)
    if days is not None:
        # Legacy support for day-based sessions
        db.create_session(user_id, token, days=days)
    else:
        # New hour-based sessions
        db.create_session(user_id, token, hours=hours)
    return token


def get_user_from_session(token: str) -> Optional[Dict[str, Any]]:
    """Get user from session token, checking both memory and Google Sheets."""
    return db.get_session_user(token)


def delete_session(token: str) -> None:
    """Delete session from both memory and Google Sheets."""
    db.delete_session(token)


def should_renew_session(token: str) -> bool:
    """Check if session should be renewed (less than 15 minutes remaining)."""
    try:
        # Get session info from database
        with db.get_conn() as conn:
            session_row = conn.execute(
                """
                SELECT expires_at FROM sessions 
                WHERE token = ? AND expires_at >= ?
                """,
                (token, db._now()),
            ).fetchone()
            
            if session_row:
                expires_at_str = session_row['expires_at']
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                current_time = datetime.utcnow()
                
                # Check if less than 15 minutes remaining
                remaining_minutes = (expires_at - current_time).total_seconds() / 60
                return remaining_minutes < 15
                
    except Exception as e:
        print(f"Error checking session renewal: {e}")
        
    return False
