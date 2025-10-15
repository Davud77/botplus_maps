# repositories/user_repository.py
"""
Репозиторий пользователей: изолирует доступ к БД.
Зависит от Database (sqlite, с row_factory=sqlite3.Row).
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from database import Database

_db = Database()


def _row_to_dict(row) -> Dict[str, Any]:
    """Безопасное преобразование sqlite3.Row → dict."""
    return {k: row[k] for k in row.keys()} if row is not None else {}


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает пользователя по username или None.
    Ожидается таблица users(id INTEGER PK, username TEXT UNIQUE, password TEXT).
    """
    cur = _db.get_cursor()
    cur.execute(
        "SELECT id, username, password FROM users WHERE username = ? LIMIT 1",
        (username,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    # Нормализуем ключи для удобства в сервисах/контроллерах
    return {"id": d.get("id"), "username": d.get("username"), "password": d.get("password")}


# (Опционально, может пригодиться дальше — не используется контроллером логина прямо сейчас)

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает пользователя по id или None."""
    cur = _db.get_cursor()
    cur.execute(
        "SELECT id, username, password FROM users WHERE id = ? LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def create_user(username: str, password_hash: str) -> int:
    """
    Создаёт пользователя с уже захешированным паролем.
    Возвращает id созданной записи.
    """
    cur = _db.get_cursor()
    cur.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, password_hash),
    )
    _db.commit()
    # sqlite lastrowid
    return int(cur.lastrowid)
