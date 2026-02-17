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
        f"🎉 Welcome to {APP_NAME}!\n\n"
        "Thank you for joining the YLN Mentorship Platform community.\n\n"
        "To complete your registration and start connecting with mentors, "
        "please use this 6-digit verification code:\n\n"
        f"    CODE: {token}\n\n"
        "Enter this code on the verification page to activate your account.\n\n"
        "⏰ This code expires in 24 hours for security.\n\n"
        "Once verified, you'll be able to:\n"
        "• Browse and connect with experienced mentors\n"
        "• Complete your mentee profile\n" 
        "• Schedule mentorship sessions\n"
        "• Access exclusive resources and opportunities\n\n"
        "If you didn't create this account, please ignore this email.\n\n"
        "YLN Mentorship Platform\n"
        "Empowering careers through meaningful connections"
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


def send_session_proposed(
    to_email: str,
    recipient_name: str,
    proposer_name: str,
    start_time: str,
    end_time: str,
) -> bool:
    subject = f"New session proposal - {APP_NAME}"
    body = (
        f"Hello {recipient_name},\n\n"
        f"{proposer_name} proposed a mentorship session.\n\n"
        f"Proposed time: {start_time} to {end_time}\n\n"
        "Please log in to accept or propose a new time."
    )
    return send_email(to_email, subject, body)


def send_session_accepted(
    mentor_email: str,
    mentee_email: str,
    mentor_name: str,
    mentee_name: str,
    start_time: str,
    end_time: str,
) -> bool:
    subject = f"Session confirmed - {APP_NAME}"
    body = (
        "Hello,\n\n"
        f"Your mentorship session is confirmed.\n\n"
        f"Mentor: {mentor_name}\n"
        f"Mentee: {mentee_name}\n"
        f"When: {start_time} to {end_time}\n\n"
        "We will send a reminder 24 hours before the meeting."
    )
    ok1 = send_email(mentor_email, subject, body)
    ok2 = send_email(mentee_email, subject, body)
    return ok1 and ok2


def send_session_reminder(
    mentor_email: str,
    mentee_email: str,
    mentor_name: str,
    mentee_name: str,
    start_time: str,
    end_time: str,
) -> bool:
    subject = f"Reminder: session tomorrow - {APP_NAME}"
    body = (
        "Hello,\n\n"
        "Reminder: your mentorship session is scheduled for tomorrow.\n\n"
        f"Mentor: {mentor_name}\n"
        f"Mentee: {mentee_name}\n"
        f"When: {start_time} to {end_time}\n\n"
        "See you soon!"
    )
    ok1 = send_email(mentor_email, subject, body)
    ok2 = send_email(mentee_email, subject, body)
    return ok1 and ok2
