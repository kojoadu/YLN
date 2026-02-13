from __future__ import annotations

import secrets
from typing import Optional, Dict, Any

from app.config import Roles
from app import db
from app.security import hash_password, verify_password


def register_user(email: str, password: str) -> tuple[bool, str, Optional[int]]:
    if not email or not email.strip().lower().endswith("@mtn.com"):
        return False, "Email must be an @mtn.com address.", None
    existing = db.get_user_by_email(email)
    if existing:
        return False, "Email already registered.", None
    user_id = db.create_user(email, hash_password(password), Roles.MENTEE)
    return True, "Registration successful. Please verify your email.", user_id


def authenticate_user(email: str, password: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
    user = db.get_user_by_email(email)
    if not user:
        return False, None, "Invalid email or password."
    if not verify_password(password, user["password_hash"]):
        return False, None, "Invalid email or password."
    if not user["is_verified"]:
        return False, None, "Email not verified. Please verify your email."
    return True, user, "Authenticated."


def create_verification_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    db.create_verification_token(user_id, token)
    return token


def verify_email_token(token: str) -> tuple[bool, str]:
    user_id = db.use_verification_token(token)
    if not user_id:
        return False, "Invalid or expired token."
    db.set_user_verified(user_id)
    return True, "Email verified. You can now log in."
