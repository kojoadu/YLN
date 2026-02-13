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
        # Special fallback for super admin if user doesn't exist in database
        from app.config import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD
        if email == SUPER_ADMIN_EMAIL and password == SUPER_ADMIN_PASSWORD:
            # Re-seed super admin if missing (useful for in-memory database)
            try:
                db.seed_super_admin()
                user = db.get_user_by_email(email)
            except Exception as e:
                print(f"Failed to re-seed super admin: {e}")
        
        if not user:
            return False, None, "Invalid email or password."
    
    # Handle missing password_hash field
    password_hash = user.get("password_hash") or user.get("password")
    if not password_hash:
        return False, None, "Invalid email or password."
    
    if not verify_password(password, password_hash):
        return False, None, "Invalid email or password."
    if not user.get("is_verified", False):
        return False, None, "Email not verified. Please verify your email."
    return True, user, "Authenticated."


def create_verification_token(user_id: int) -> str:
    """Generate a 6-digit verification code."""
    import random
    token = str(random.randint(100000, 999999))
    db.create_verification_token(user_id, token)
    return token


def verify_email_token(token: str) -> tuple[bool, str]:
    user_id = db.use_verification_token(token)
    if not user_id:
        return False, "Invalid or expired token."
    db.set_user_verified(user_id)
    return True, "Email verified. You can now log in."


def send_verification_email(email: str, verification_token: str, base_url: str = "http://localhost:8501") -> bool:
    """Send verification email to user."""
    from app.config import (
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TLS
    )
    
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        print("SMTP configuration incomplete")
        return False
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Create email content
        subject = "Welcome to YLN Mentorship Platform - Verify Your Email"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #722F37 0%, #8B4513 100%); color: #F5DEB3; text-align: center; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #ddd; border-top: none; }}
                .code {{ background: #f8f9fa; border: 2px solid #722F37; border-radius: 8px; font-size: 28px; font-weight: bold; text-align: center; padding: 20px; margin: 20px 0; color: #722F37; font-family: 'Courier New', monospace; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to YLN Mentorship!</h1>
                </div>
                <div class="content">
                    <h2>Thank you for joining us!</h2>
                    <p>We're excited to have you as part of the YLN Mentorship Platform community.</p>
                    <p>To complete your registration and start connecting with mentors, please enter this verification code on the platform:</p>
                    
                    <div class="code">{verification_token}</div>
                    
                    <p>Once verified, you'll be able to:</p>
                    <ul>
                        <li>Browse and connect with experienced mentors</li>
                        <li>Complete your mentee profile</li>
                        <li>Schedule mentorship sessions</li>
                        <li>Access exclusive resources and opportunities</li>
                    </ul>
                    
                    <hr>
                    <p><strong>Important:</strong> This code expires in 24 hours for security purposes.</p>
                    <p><small>If you didn't create this account, please ignore this email.</small></p>
                </div>
                <div class="footer">
                    <p>YLN Mentorship Platform<br>
                    Empowering careers through meaningful connections</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = email
        
        # Add HTML content
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            
        print(f"Verification email sent to {email}")
        return True
        
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False


def send_password_reset_email(email: str, reset_token: str, base_url: str = "http://localhost:8501") -> bool:
    """Send password reset email to user."""
    from app.config import (
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TLS
    )
    
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        print("SMTP configuration incomplete")
        return False
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Create reset link
        reset_link = f"{base_url}?page=reset_password&token={reset_token}"
        
        # Create email content
        subject = "Password Reset - YLN Mentorship Platform"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #722F37 0%, #8B4513 100%); color: #F5DEB3; text-align: center; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #ddd; border-top: none; }}
                .button {{ background: #722F37; color: #F5DEB3; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔑 Password Reset Request</h1>
                </div>
                <div class="content">
                    <h2>Hello!</h2>
                    <p>We received a request to reset your password for your YLN Mentorship Platform account.</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_link}" class="button">Reset My Password</a>
                    <p><strong>This link will expire in 1 hour.</strong></p>
                    <p>If you didn't request a password reset, you can safely ignore this email.</p>
                    <hr>
                    <p><small>If the button doesn't work, copy and paste this link into your browser:<br>
                    {reset_link}</small></p>
                </div>
                <div class="footer">
                    <p>YLN Mentorship Platform<br>
                    This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = email
        
        # Add HTML content
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            
        print(f"Password reset email sent to {email}")
        return True
        
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
        return False
