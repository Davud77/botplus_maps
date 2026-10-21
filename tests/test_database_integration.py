"""Real PostgreSQL checks. Only TEST_DATABASE_URL is used, never application .env."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from server.database import Database

TEST_DSN = os.environ.get("TEST_DATABASE_URL")
if os.environ.get("REQUIRE_DATABASE_TESTS") == "1" and not TEST_DSN:
    raise RuntimeError("TEST_DATABASE_URL is required for database CI tests")


@unittest.skipUnless(TEST_DSN, "Set TEST_DATABASE_URL to an isolated disposable PostgreSQL database")
class DatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(TEST_DSN)
        cls.schema = "scope_test_" + uuid4().hex
        cls.table = sql.Identifier(cls.schema, "probe")
        with cls.db.cursor(write=True) as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
            cursor.execute(sql.SQL("CREATE TABLE {} (token text PRIMARY KEY)").format(cls.table))

    @classmethod
    def tearDownClass(cls):
        with cls.db.cursor(write=True) as cursor:
            cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.db.cursor(write=True) as cursor:
            cursor.execute(sql.SQL("TRUNCATE {}").format(self.table))

    def tokens(self):
        with self.db.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT token FROM {} ORDER BY token").format(self.table))
            return [row["token"] for row in cursor.fetchall()]

    def test_concurrent_commit_and_rollback_are_isolated(self):
        barrier = threading.Barrier(2)
        connections, errors, pids = [], [], []

        def operation(token, fail):
            try:
                with self.db.cursor(write=True) as cursor:
                    connections.append(cursor.connection)
                    cursor.execute("SELECT pg_backend_pid() AS pid")
                    pids.append(cursor.fetchone()["pid"])
                    cursor.execute(sql.SQL("INSERT INTO {} VALUES (%s)").format(self.table), (token,))
                    barrier.wait(timeout=5)
                    if fail:
                        raise ValueError("expected rollback")
            except ValueError:
                if not fail:
                    errors.append("unexpected ValueError")
            except BaseException as error:
                errors.append(repr(error))

        workers = [threading.Thread(target=operation, args=("committed", False)),
                   threading.Thread(target=operation, args=("rolled_back", True))]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertEqual(len(set(pids)), 2)
        self.assertTrue(all(connection.closed for connection in connections))
        self.assertEqual(self.tokens(), ["committed"])

    def test_read_is_readonly_and_cannot_accidentally_commit_writes(self):
        with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
            with self.db.cursor() as cursor:
                cursor.execute(sql.SQL("INSERT INTO {} VALUES ('unexpected')").format(self.table))
        self.assertEqual(self.tokens(), [])

    def test_write_error_is_rolled_back_and_next_operation_works(self):
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            with self.db.cursor(write=True) as cursor:
                cursor.execute(sql.SQL("INSERT INTO {} VALUES ('failed')").format(self.table))
                cursor.execute("SELECT 1 / 0")
        with self.db.cursor(write=True) as cursor:
            cursor.execute(sql.SQL("INSERT INTO {} VALUES ('next')").format(self.table))
        self.assertEqual(self.tokens(), ["next"])

    def test_early_return_closes_cursor_and_connection(self):
        resources = []

        def read():
            with self.db.cursor() as cursor:
                resources.extend([cursor, cursor.connection])
                cursor.execute("SELECT 7 AS value")
                return cursor.fetchone()["value"]

        self.assertEqual(read(), 7)
        self.assertTrue(all(resource.closed for resource in resources))

    def test_statement_timeout_cancels_query_and_releases_transaction(self):
        db = Database(TEST_DSN, statement_timeout_ms=50)
        with self.assertRaises(psycopg2.errors.QueryCanceled):
            with db.cursor() as cursor:
                connection = cursor.connection
                cursor.execute("SELECT pg_sleep(1)")
        self.assertTrue(connection.closed)
        with self.db.cursor() as cursor:
            cursor.execute("SELECT 1 AS value")
            self.assertEqual(cursor.fetchone()["value"], 1)

    def test_idle_transaction_timeout_does_not_poison_next_operation(self):
        db = Database(TEST_DSN, idle_transaction_timeout_ms=100)
        with self.assertRaises(psycopg2.OperationalError):
            with db.cursor() as cursor:
                connection = cursor.connection
                time.sleep(.3)
                cursor.execute("SELECT 1")
        self.assertTrue(connection.closed)
        self.assertEqual(self.tokens(), [])

    def test_nested_scopes_are_independent_transactions(self):
        with self.assertRaises(ValueError):
            with self.db.cursor(write=True) as outer:
                outer.execute(sql.SQL("INSERT INTO {} VALUES ('outer')").format(self.table))
                with self.db.cursor(write=True) as inner:
                    inner.execute(sql.SQL("INSERT INTO {} VALUES ('inner')").format(self.table))
                raise ValueError("rollback outer only")
        self.assertEqual(self.tokens(), ["inner"])

    def test_transaction_local_settings_do_not_survive_commit(self):
        connection = self.db.connect(dict_rows=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW statement_timeout")
                baseline = cursor.fetchone()[0]
                self.db.configure_transaction(cursor)
                cursor.execute("SHOW statement_timeout")
                self.assertEqual(cursor.fetchone()[0], "30s")
            connection.commit()
            with connection.cursor() as cursor:
                cursor.execute("SHOW statement_timeout")
                self.assertEqual(cursor.fetchone()[0], baseline)
        finally:
            Database.release(connection)

    def test_gevent_database_waits_do_not_block_the_event_loop(self):
        # Monkey-patching happens before imports in a separate process, like Gunicorn.
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("gevent_database_probe.py"))],
                                env=os.environ.copy(), capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("gevent isolation passed", result.stdout)

