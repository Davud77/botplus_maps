# server/database.py
"""
Подключение к PostgreSQL/PostGIS через пул соединений (psycopg2).
Интерфейс совместим с прежним SQLite-классом:
  - connect()
  - get_cursor()
  - commit()
  - close()

Дополнительно предоставлен контекстный менеджер get_connection().
"""

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

import config

# Пул соединений создаётся лениво при первом обращении,
# чтобы избежать конфликтов при импортировании в воркерах gunicorn.
_POOL: Optional[SimpleConnectionPool] = None


def _ensure_pool() -> SimpleConnectionPool:
    global _POOL
    if _POOL is None:
        # keepalives улучшают стабильность долгоживущих соединений
        _POOL = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=config.DATABASE_DSN,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )
    return _POOL


@contextmanager
def get_connection():
    """
    Контекстный менеджер для «сырых» операций.
    Возвращает соединение, на котором autocommit=False; по выходу — commit/rollback.
    """
    pool = _ensure_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


class Database:
    """
    Класс-обёртка с тем же интерфейсом, что и под SQLite.
    Возвращает курсор RealDictCursor (строки как dict).
    """
    def __init__(self):
        self._conn = None

    def connect(self):
        if self._conn is None:
            pool = _ensure_pool()
            self._conn = pool.getconn()
            self._conn.autocommit = False

    def get_cursor(self):
        self.connect()
        # Реестр в dict-подобном виде
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def commit(self):
        if self._conn:
            self._conn.commit()

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            finally:
                # Возвращаем соединение в пул
                _ensure_pool().putconn(self._conn)
            self._conn = None
