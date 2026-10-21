import contextlib
import io
import unittest
from unittest.mock import patch
import psycopg2
from server.init_pg_auth import init_auth_db


class BootstrapFailureTests(unittest.TestCase):
    def test_failed_initialization_is_not_reported_as_success(self):
        with patch("server.init_pg_auth.Database") as factory:
            factory.return_value.cursor.return_value.__enter__.side_effect = psycopg2.OperationalError("test failure")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with self.assertRaises(psycopg2.OperationalError):
                    init_auth_db()
            self.assertNotIn("initialized successfully", output.getvalue())
