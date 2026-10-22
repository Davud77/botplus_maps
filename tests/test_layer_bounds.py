import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from flask import Flask
from psycopg2 import extensions, sql
from server.database import Database
from server.controllers import layer_bounds_controller as bounds
from server.http_policies import register_http_policies


@unittest.skipUnless(os.environ.get('TEST_POSTGIS') == '1', 'Requires disposable PostGIS')
class LayerBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(os.environ['TEST_DATABASE_URL'])
        cls.name = extensions.parse_dsn(os.environ['TEST_DATABASE_URL'])['dbname']
        cls.schema = 'bounds_' + uuid4().hex[:12]
        with cls.db.cursor(write=True) as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS postgis')
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
            cur.execute(sql.SQL('CREATE TABLE {}.points (geom geometry(Point,3857))').format(sql.Identifier(cls.schema)))
            cur.execute(sql.SQL('INSERT INTO {}.points VALUES (ST_Transform(ST_SetSRID(ST_Point(47,43),4326),3857)), (ST_Transform(ST_SetSRID(ST_Point(48,44),4326),3857))').format(sql.Identifier(cls.schema)))
            cur.execute(sql.SQL('CREATE TABLE {}.empty (geom geometry(Point,4326))').format(sql.Identifier(cls.schema)))
            cur.execute(sql.SQL('CREATE TABLE {}.unknown_crs (geom geometry)').format(sql.Identifier(cls.schema)))
        cls.app = Flask(__name__)
        register_http_policies(cls.app, lambda token: {'uid': 1} if token == 'valid' else None, lambda origin: False)
        cls.app.register_blueprint(bounds.bounds_blueprint, url_prefix='/api')
        cls.patcher = patch.object(bounds, 'database', cls.db)
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        with cls.db.cursor(write=True) as cur:
            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        self.client = self.app.test_client()
        self.client.set_cookie('access_token', 'valid')

    def get(self, table):
        return self.client.get('/api/layers/bounds', query_string={'kind':'vector','dbName':self.name,'schema':self.schema,'tableName':table})

    def test_projected_geometry_returns_wgs84_without_feature_download(self):
        response = self.get('points')
        self.assertEqual(response.status_code, 200)
        result = response.json
        self.assertEqual(set(result), {'bounds','estimated'})
        for key, expected in {'west':47,'east':48,'south':43,'north':44}.items():
            self.assertAlmostEqual(result['bounds'][key], expected, places=5)

    def test_empty_layer_and_missing_crs_have_explicit_results(self):
        self.assertIsNone(self.get('empty').json['bounds'])
        self.assertEqual(self.get('unknown_crs').status_code, 422)
        self.assertEqual(self.get("points';DROP TABLE points;--").status_code, 404)

    def test_extent_requires_authentication(self):
        self.assertEqual(self.app.test_client().get('/api/layers/bounds?kind=panoramas').status_code, 401)
