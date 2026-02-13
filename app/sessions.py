from __future__ import annotations

import secrets
from typing import Optional, Dict, Any

from app import db


def create_session(user_id: int, days: int = 7) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session(user_id, token, days=days)
    return token


def get_user_from_session(token: str) -> Optional[Dict[str, Any]]:
    return db.get_session_user(token)


def delete_session(token: str) -> None:
    db.delete_session(token)
