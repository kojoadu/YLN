from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.config import DB_PATH, Roles, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD
from app.security import hash_password


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


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
            """
        )

    seed_super_admin()


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
        return int(cur.lastrowid)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def set_user_verified(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))


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
