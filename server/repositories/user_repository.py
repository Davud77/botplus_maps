"""User repository; each call completes and releases its PostgreSQL transaction."""
from typing import Optional, Dict, Any

try:
    from ..database import Database
except ImportError:
    from database import Database


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with Database().cursor() as cursor:
        cursor.execute("SELECT id, username, password, role, is_active, session_version FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with Database().cursor() as cursor:
        cursor.execute("SELECT id, username, password, role, is_active, session_version FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(username: str, password_hash: str) -> int:
    with Database().cursor(write=True) as cursor:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
                       (username, password_hash))
        return cursor.fetchone()["id"]
