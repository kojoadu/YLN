from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_TLS, SMTP_USER, APP_NAME


def _smtp_ready() -> bool:
    """Check if SMTP configuration is complete."""
    ready = all([SMTP_HOST, SMTP_USER, SMTP_PASS])
    if not ready:
        print(f"SMTP Configuration incomplete:")
        print(f"  SMTP_HOST: {'✓' if SMTP_HOST else '✗'} ({SMTP_HOST})")
        print(f"  SMTP_USER: {'✓' if SMTP_USER else '✗'} ({SMTP_USER})")
        print(f"  SMTP_PASS: {'✓' if SMTP_PASS else '✗'} ({'***' if SMTP_PASS else 'EMPTY'})")
        print(f"  SMTP_PORT: {SMTP_PORT}")
        print(f"  SMTP_TLS: {SMTP_TLS}")
        print(f"  SMTP_FROM: {SMTP_FROM}")
    return ready


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email with proper error handling and return status."""
    if not _smtp_ready():
        print(f"[EMAIL MOCK] SMTP not configured. To: {to_email}\nSubject: {subject}\n{body}\n")
        print(f"SMTP Config: HOST={SMTP_HOST}, USER={SMTP_USER}, PASS={'***' if SMTP_PASS else 'EMPTY'}")
        return False

    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    """Send verification email and return success status."""
    subject = f"Verify your email - {APP_NAME}"
    body = (
        f"Welcome to {APP_NAME}!\n\n"
        "Use the verification code below to verify your email:\n"
        f"{token}\n\n"
        "This code expires in 24 hours."
    )
    return send_email(to_email, subject, body)


def send_mentor_assigned_to_mentor(mentor_email: str, mentor_name: str, mentee_name: str) -> bool:
    """Send mentor assignment email to mentor."""
    subject = f"New mentee assigned - {APP_NAME}"
    body = (
        f"Hello {mentor_name},\n\n"
        f"You have been assigned a new mentee: {mentee_name}.\n"
        "Please log in to view details."
    )
    return send_email(mentor_email, subject, body)


def send_mentor_assigned_to_mentee(mentee_email: str, mentee_name: str, mentor_name: str) -> bool:
    """Send mentor assignment email to mentee."""
    subject = f"Your mentor is confirmed - {APP_NAME}"
    body = (
        f"Hello {mentee_name},\n\n"
        f"Your mentor is {mentor_name}.\n"
        "We will be in touch with next steps."
    )
    return send_email(mentee_email, subject, body)
