"""Failure/cleanup checks that do not require a PostgreSQL server."""
import os
import unittest
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extensions import parse_dsn
from server.database import Database


class DatabaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.factory = Database("dbname=fixture user=fixture")
        self.connection = MagicMock()
        self.connection.closed = False
        self.connection.autocommit = False
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.connect = patch("server.database.psycopg2.connect", return_value=self.connection).start()
        self.addCleanup(patch.stopall)

    def test_read_completes_transaction_and_closes_connection(self):
        with self.factory.cursor() as cursor:
            cursor.execute("SELECT 1")
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()
        self.cursor.execute.assert_any_call("SET TRANSACTION READ ONLY")

    def test_write_commits_only_after_clean_exit(self):
        with self.factory.cursor(write=True):
            self.connection.commit.assert_not_called()
        self.connection.commit.assert_called_once()
        self.connection.close.assert_called_once()

    def test_error_rolls_back_and_preserves_exception(self):
        failure = ValueError("operation failed")
        with self.assertRaises(ValueError) as caught:
            with self.factory.cursor(write=True):
                raise failure
        self.assertIs(caught.exception, failure)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_cancellation_also_closes_connection(self):
        class Cancelled(BaseException):
            pass
        with self.assertRaises(Cancelled):
            with self.factory.cursor(write=True):
                raise Cancelled()
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_commit_failure_rolls_back_and_closes(self):
        self.connection.commit.side_effect = psycopg2.OperationalError("commit failed")
        with self.assertRaises(psycopg2.OperationalError):
            with self.factory.cursor(write=True):
                pass
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_rollback_failure_does_not_hide_operation_error_or_leak_connection(self):
        self.connection.rollback.side_effect = psycopg2.OperationalError("connection lost")
        with self.assertLogs("server.database", level="WARNING"):
            with self.assertRaisesRegex(ValueError, "original"):
                with self.factory.cursor(write=True):
                    raise ValueError("original")
        self.connection.close.assert_called_once()

    def test_cursor_initialization_failure_still_closes(self):
        self.connection.cursor.side_effect = psycopg2.InterfaceError("cursor failed")
        with self.assertRaises(psycopg2.InterfaceError):
            with self.factory.cursor():
                pass
        self.connection.close.assert_called_once()

    def test_database_override_preserves_deployment_connection_settings(self):
        factory = Database("dbname=main user=custom password=unit-test-only host=db.internal port=6432 sslmode=require")
        connection = factory.connect("vectors", dict_rows=False)
        dsn = parse_dsn(self.connect.call_args.args[0])
        self.assertEqual(dsn["dbname"], "vectors")
        self.assertEqual(dsn["host"], "db.internal")
        self.assertEqual(dsn["port"], "6432")
        self.assertEqual(dsn["user"], "custom")
        self.assertEqual(dsn["sslmode"], "require")
        self.assertEqual(self.connect.call_args.kwargs["connect_timeout"], 5)
        Database.release(connection)

    def test_setup_failure_closes_connection(self):
        self.cursor.execute.side_effect = psycopg2.ProgrammingError("setup failed")
        with self.assertRaises(psycopg2.ProgrammingError):
            with self.factory.cursor():
                pass
        self.connection.close.assert_called_once()

    def test_timeouts_are_validated(self):
        with patch.dict(os.environ, {"DB_STATEMENT_TIMEOUT_MS": "0"}):
            with self.assertRaises(ValueError):
                Database("dbname=fixture")
