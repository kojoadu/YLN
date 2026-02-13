from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv("YLN_DB_PATH", str(DATA_DIR / "yln.db"))

SUPER_ADMIN_EMAIL = os.getenv("YLN_SUPER_ADMIN_EMAIL", "admin@yln.local")
SUPER_ADMIN_PASSWORD = os.getenv("YLN_SUPER_ADMIN_PASSWORD", "admin1234")

SMTP_HOST = os.getenv("YLN_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("YLN_SMTP_PORT", "587"))
SMTP_USER = os.getenv("YLN_SMTP_USER", "")
SMTP_PASS = os.getenv("YLN_SMTP_PASS", "")
SMTP_FROM = os.getenv("YLN_SMTP_FROM", "noreply@yln.local")
SMTP_TLS = os.getenv("YLN_SMTP_TLS", "true").lower() == "true"

APP_NAME = "Yello Ladies Network Mentorship"

@dataclass(frozen=True)
class Roles:
    ADMIN: str = "admin"
    MENTEE: str = "mentee"
