# server/repositories/user_repository.py
"""
Репозиторий пользователей: доступ к БД PostgreSQL (psycopg2).
Интерфейс:
  - get_user_by_username(username) -> Optional[dict]
  - get_user_by_id(user_id) -> Optional[dict]
  - create_user(username, password_hash) -> int (id)
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Mapping

from database import Database

_db = Database()


def _row_to_dict(row) -> Dict[str, Any]:
    """Нормализуем строку курсора в dict (RealDictCursor уже отдаёт dict)."""
    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {}


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает пользователя по username или None.
    Таблица: users(id SERIAL PK, username TEXT UNIQUE, password TEXT).
    """
    cur = _db.get_cursor()
    cur.execute(
        "SELECT id, username, password FROM users WHERE username = %s LIMIT 1",
        (username,),
    )
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает пользователя по id или None."""
    cur = _db.get_cursor()
    cur.execute(
        "SELECT id, username, password FROM users WHERE id = %s LIMIT 1",
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
        "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
        (username, password_hash),
    )
    row = cur.fetchone()
    _db.commit()
    return int(row["id"])
