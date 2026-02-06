# repositories/user_repository.py
"""
Репозиторий пользователей: изолирует доступ к БД (PostgreSQL).
"""

from __future__ import annotations
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any

def _get_db_connection():
    """
    Создает соединение с PostgreSQL.
    Использует DATABASE_URL из переменных окружения (как в контроллерах).
    """
    dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db")
    return psycopg2.connect(dsn)

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает пользователя по username или None.
    Таблица: users(id SERIAL PK, username VARCHAR, password VARCHAR).
    """
    conn = None
    try:
        conn = _get_db_connection()
        # RealDictCursor позволяет получать результаты сразу как словарь
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, password FROM users WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
            
            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"DB Error (get_user_by_username): {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает пользователя по id или None.
    """
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, password FROM users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"DB Error (get_user_by_id): {e}")
        return None
    finally:
        if conn:
            conn.close()

def create_user(username: str, password_hash: str) -> Optional[int]:
    """
    Создаёт пользователя с уже захешированным паролем.
    Возвращает id созданной записи.
    """
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            # В PostgreSQL используем RETURNING id вместо lastrowid
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
                (username, password_hash)
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return new_id
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DB Error (create_user): {e}")
        return None
    finally:
        if conn:
            conn.close()