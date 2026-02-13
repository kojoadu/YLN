from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = ROOT_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    safe_name = f"{int(datetime.utcnow().timestamp())}_{uploaded_file.name}"
    file_path = UPLOADS_DIR / safe_name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(file_path)


def safe_image(image_ref: str, width: int) -> None:
    if not image_ref:
        return
    cleaned = str(image_ref).strip()
    if (cleaned.startswith("\"") and cleaned.endswith("\"")) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1]
    try:
        st.image(cleaned, width=width)
    except Exception:
        st.warning("Profile image not available.")
