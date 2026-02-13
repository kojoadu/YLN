from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_TLS, SMTP_USER, APP_NAME


def _smtp_ready() -> bool:
    return all([SMTP_HOST, SMTP_USER, SMTP_PASS])


def send_email(to_email: str, subject: str, body: str) -> None:
    if not _smtp_ready():
        print(f"[EMAIL MOCK] To: {to_email}\nSubject: {subject}\n{body}\n")
        return

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


def send_verification_email(to_email: str, token: str) -> None:
    subject = f"Verify your email - {APP_NAME}"
    body = (
        f"Welcome to {APP_NAME}!\n\n"
        "Use the verification code below to verify your email:\n"
        f"{token}\n\n"
        "This code expires in 24 hours."
    )
    send_email(to_email, subject, body)


def send_mentor_assigned_to_mentor(mentor_email: str, mentor_name: str, mentee_name: str) -> None:
    subject = f"New mentee assigned - {APP_NAME}"
    body = (
        f"Hello {mentor_name},\n\n"
        f"You have been assigned a new mentee: {mentee_name}.\n"
        "Please log in to view details."
    )
    send_email(mentor_email, subject, body)


def send_mentor_assigned_to_mentee(mentee_email: str, mentee_name: str, mentor_name: str) -> None:
    subject = f"Your mentor is confirmed - {APP_NAME}"
    body = (
        f"Hello {mentee_name},\n\n"
        f"Your mentor is {mentor_name}.\n"
        "We will be in touch with next steps."
    )
    send_email(mentee_email, subject, body)
