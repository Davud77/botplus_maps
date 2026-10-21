"""Short, isolated PostgreSQL transactions; no connection is stored on a controller."""
from contextlib import contextmanager
import logging
import os

import psycopg2
from psycopg2 import extensions
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _enable_cooperative_io():
    """Gunicorn's gevent socket patch does not make libpq cooperative by itself."""
    try:
        from gevent.monkey import is_module_patched
    except ImportError:
        return
    if is_module_patched("socket") and extensions.get_wait_callback() is None:
        from psycogreen.gevent import patch_psycopg
        patch_psycopg()


def _setting(name, default, minimum):
    value = int(os.environ.get(name, default))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


class Database:
    """Reusable factory. Each cursor context owns its connection.

    Reads are read-only and roll back on exit. Writes commit only after a clean
    exit; errors, including cancellations, roll back. Nested contexts are separate
    transactions, so multi-statement atomic operations must use one context.
    """

    LEGACY_SCHEMA_LOCK = 941027001

    def __init__(self, dsn=None, *, connect_timeout=None, statement_timeout_ms=None,
                 idle_transaction_timeout_ms=None):
        if dsn is None:
            try:
                from .config import DATABASE_URL
            except ImportError:
                from config import DATABASE_URL
            dsn = DATABASE_URL
        self._dsn = dsn
        self.connect_timeout = (connect_timeout if connect_timeout is not None
                                else _setting("DB_CONNECT_TIMEOUT_SECONDS", 5, 1))
        self.statement_timeout_ms = (statement_timeout_ms if statement_timeout_ms is not None
                                     else _setting("DB_STATEMENT_TIMEOUT_MS", 30000, 1))
        self.idle_transaction_timeout_ms = (idle_transaction_timeout_ms if idle_transaction_timeout_ms is not None
                                            else _setting("DB_IDLE_TRANSACTION_TIMEOUT_MS", 10000, 1))
        if min(self.connect_timeout, self.statement_timeout_ms, self.idle_transaction_timeout_ms) <= 0:
            raise ValueError("Database timeouts must be positive")

    def connect(self, database_name=None, *, dict_rows=True, autocommit=False):
        """Open a fresh connection. Low-level callers must close it themselves."""
        _enable_cooperative_io()
        dsn = (extensions.make_dsn(self._dsn, dbname=database_name)
               if database_name is not None else self._dsn)
        kwargs = {"connect_timeout": self.connect_timeout}
        if dict_rows:
            kwargs["cursor_factory"] = RealDictCursor
        connection = psycopg2.connect(dsn, **kwargs)
        try:
            connection.autocommit = autocommit
            return connection
        except BaseException:
            connection.close()
            raise

    def configure_transaction(self, cursor, *, read_only=False):
        # SET LOCAL is compatible with transaction-mode PgBouncer. Settings must
        # not leak to its next client; libpq startup options are intentionally unused.
        if read_only:
            cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = %s", (self.statement_timeout_ms,))
        cursor.execute("SET LOCAL idle_in_transaction_session_timeout = %s",
                       (self.idle_transaction_timeout_ms,))

    @staticmethod
    def release(connection):
        """End any remaining transaction and close, even when rollback fails."""
        if connection is None:
            return
        try:
            if not connection.closed and not connection.autocommit:
                connection.rollback()
        except Exception:
            logger.warning("PostgreSQL rollback failed during cleanup")
        finally:
            try:
                connection.close()
            except Exception:
                logger.warning("PostgreSQL connection cleanup failed")

    @contextmanager
    def cursor(self, *, write=False, dict_rows=True, database_name=None):
        connection = self.connect(database_name, dict_rows=dict_rows)
        try:
            with connection.cursor() as cursor:
                self.configure_transaction(cursor, read_only=not write)
                yield cursor
            if write:
                connection.commit()
            # Reads and errors roll back in release(). No implicit write commit.
        finally:
            self.release(connection)
