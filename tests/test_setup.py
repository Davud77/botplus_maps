"""First-run setup validation and HTTP security without external services."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from controllers import setup_controller as setup
from http_policies import register_http_policies


class SetupTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        register_http_policies(app, lambda token: None, lambda origin: False)
        app.register_blueprint(setup.setup_blueprint, url_prefix='/api/setup')
        self.client = app.test_client()

    def test_invalid_credentials_are_rejected_before_database_access(self):
        for data in [[], {}, {'username': 42, 'password': 'long-enough-password'},
                     {'username': '../etc', 'password': 'long-enough-password'},
                     {'username': 'ab', 'password': 'long-enough-password'},
                     {'username': 'admin', 'password': 'short'},
                     {'username': 'admin', 'password': ' ' * 12},
                     {'username': 'admin', 'password': 'x' * 129}]:
            with self.subTest(data=data), patch.object(setup, 'Database') as database:
                response = self.client.post('/api/setup/initialize', json=data)
                self.assertEqual(response.status_code, 400)
                database.assert_not_called()

    def test_cross_site_setup_cannot_claim_installation(self):
        with patch.object(setup, 'Database') as database:
            response = self.client.post('/api/setup/initialize', json={}, headers={'Origin': 'https://attacker.example'})
            self.assertEqual(response.status_code, 403)
            database.assert_not_called()

    def test_closed_setup_does_not_hash_or_replace_credentials(self):
        with patch.object(setup, 'setup_required', return_value=False), patch.object(setup, 'generate_password_hash') as hashing:
            response = self.client.post('/api/setup/initialize', json={'username': 'admin', 'password': 'long-enough-password'})
            self.assertEqual(response.status_code, 409)
            hashing.assert_not_called()

    def test_database_outage_returns_retriable_status_without_details(self):
        with patch.object(setup, 'Database', side_effect=RuntimeError('private password and host')):
            response = self.client.get('/api/setup/status')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private', response.get_data(as_text=True))
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_atomic_recheck_rejects_second_worker(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {'initialized': True}
        with patch.object(setup, 'setup_required', return_value=True), patch.object(setup, 'Database') as database:
            database.return_value.cursor.return_value.__enter__.return_value = cursor
            response = self.client.post('/api/setup/initialize', json={'username': 'admin', 'password': 'long-enough-password'})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(cursor.execute.call_count, 2)


if __name__ == '__main__':
    unittest.main()
