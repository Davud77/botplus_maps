"""Enrollment races and upgrade behavior in an isolated schema of the test DB."""
import os
from pathlib import Path
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from flask import Flask
from psycopg2 import sql, extensions
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from database import Database
from controllers import setup_controller as setup
from init_pg_auth import init_auth_db


@unittest.skipUnless(os.environ.get('TEST_POSTGIS') == '1', 'requires isolated PostGIS test database')
class SetupIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Database(os.environ['TEST_DATABASE_URL'])
        self.schema = 'setup_' + uuid4().hex
        with self.root.cursor(write=True) as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.dsn = extensions.make_dsn(os.environ['TEST_DATABASE_URL'], options=f'-c search_path={self.schema},public')
        self.db = Database(self.dsn)
        self.addCleanup(self.cleanup_schema)
        with patch.dict(os.environ, {'DATABASE_URL': self.dsn}):
            init_auth_db()
        self.factory = patch.object(setup, 'Database', return_value=self.db)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(setup.setup_blueprint, url_prefix='/api/setup')
        self.client = self.app.test_client()

    def cleanup_schema(self):
        with self.root.cursor(write=True) as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def enroll(self, client=None, username='owner'):
        return (client or self.client).post('/api/setup/initialize', json={'username': username, 'password': ' secure test password '})

    def test_first_admin_is_hashed_and_setup_stays_closed_after_restart(self):
        self.assertTrue(self.client.get('/api/setup/status').get_json()['setup_required'])
        response = self.enroll()
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        with self.db.cursor() as cursor:
            cursor.execute('SELECT username, password, role FROM users')
            owner = cursor.fetchone()
            self.assertEqual(owner['username'], 'owner')
            self.assertEqual(owner['role'], 'admin')
            self.assertTrue(check_password_hash(owner['password'], ' secure test password '))
        with patch.dict(os.environ, {'DATABASE_URL': self.dsn}):
            init_auth_db()
        self.assertFalse(self.client.get('/api/setup/status').get_json()['setup_required'])
        self.assertEqual(self.enroll(username='intruder').status_code, 409)
        with self.db.cursor(write=True) as cursor:
            cursor.execute('DELETE FROM users')
        self.assertFalse(self.client.get('/api/setup/status').get_json()['setup_required'])

    def test_concurrent_workers_create_exactly_one_administrator(self):
        barrier = threading.Barrier(2)
        def attempt(index):
            barrier.wait(timeout=10)
            return self.enroll(self.app.test_client(), f'owner{index}').status_code
        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(attempt, range(2)))
        self.assertEqual(sorted(statuses), [201, 409])
        with self.db.cursor() as cursor:
            cursor.execute('SELECT count(*) AS count FROM users')
            self.assertEqual(cursor.fetchone()['count'], 1)
            cursor.execute('SELECT count(*) AS count FROM app_installation')
            self.assertEqual(cursor.fetchone()['count'], 1)

    def test_legacy_installation_preserves_credentials_and_never_seeds_defaults(self):
        password_hash = generate_password_hash('existing-owner-password')
        with self.db.cursor(write=True) as cursor:
            cursor.execute('INSERT INTO users (username,password) VALUES (%s,%s)', ('existing', password_hash))
            cursor.execute('ALTER TABLE users DROP COLUMN role')
        with patch.dict(os.environ, {'DATABASE_URL': self.dsn, 'DEFAULT_ADMIN_USERNAME': 'must_not_be_seeded'}):
            init_auth_db()
        self.assertFalse(self.client.get('/api/setup/status').get_json()['setup_required'])
        self.assertEqual(self.enroll().status_code, 409)
        with self.db.cursor() as cursor:
            cursor.execute('SELECT username,password FROM users')
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['username'], 'existing')
        self.assertEqual(rows[0]['password'], password_hash)
