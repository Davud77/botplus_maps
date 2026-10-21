"""Actual PostGIS manager and HTTP routes, using only a disposable test database."""
import os
import unittest
import threading
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from flask import Flask, Response
from psycopg2 import extensions, sql
from server.database import Database
from server.controllers.pano_controller import PanoController, create_pano_blueprint
from server.managers.ortho_manager import OrthoManager
from server.managers.pano_manager import PanoManager
from server.models.ortho import Ortho
from server.http_policies import register_http_policies
from server.controllers import vector


class TrackingDatabase(Database):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connections = []

    def connect(self, *args, **kwargs):
        connection = super().connect(*args, **kwargs)
        self.connections.append(connection)
        return connection


class StorageProbe:
    client = True
    bucket_name = "test-panoramas"

    def __init__(self, database):
        self.database = database
        self.deleted = []

    def assert_released(self):
        assert all(c.closed for c in self.database.connections), "DB connection held during object storage I/O"

    def send_local_file(self, filename, mimetype=None):
        self.assert_released()
        return Response(b"test-preview", mimetype=mimetype)

    def delete_file(self, filename):
        self.assert_released()
        self.deleted.append(filename)


@unittest.skipUnless(os.environ.get("TEST_POSTGIS") == "1", "TEST_POSTGIS=1 requires an isolated PostGIS test database")
class PostgisPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("TEST_DATABASE_URL"):
            raise RuntimeError("TEST_DATABASE_URL is required")
        cls.db = TrackingDatabase(os.environ["TEST_DATABASE_URL"])
        with cls.db.cursor(write=True) as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cls.controller = PanoController.__new__(PanoController)
        cls.controller.db = cls.db
        cls.controller.pano_bucket = "test-panoramas"
        cls.controller.storage = StorageProbe(cls.db)
        cls.controller._ensure_table()
        cls.orthos = OrthoManager(cls.db)
        cls.panos = PanoManager(cls.db)
        cls.app = Flask(__name__)
        cls.app.config["TESTING"] = True
        register_http_policies(cls.app, lambda token: {"uid": 1} if token == "valid" else None,
                               lambda origin: False)
        cls.app.register_blueprint(create_pano_blueprint(cls.controller), url_prefix="/api")
        cls.app.register_blueprint(vector.vector_bp, url_prefix="/api")
        cls.vector_database = patch.object(vector, "database", cls.db)
        cls.vector_database.start()
        cls.db_name = extensions.parse_dsn(os.environ["TEST_DATABASE_URL"])["dbname"]

    @classmethod
    def tearDownClass(cls):
        cls.vector_database.stop()

    def setUp(self):
        with self.db.cursor(write=True) as cursor:
            cursor.execute("TRUNCATE public.photos_4326, orthophotos RESTART IDENTITY")
        self.client = self.app.test_client()
        self.client.set_cookie("access_token", "valid")
        self.controller.storage.deleted.clear()
        self.db.connections.clear()

    def assert_released(self):
        self.assertTrue(self.db.connections)
        self.assertTrue(all(c.closed for c in self.db.connections))

    def insert_pano(self):
        self.controller._insert_pano_db("test.jpg", "test.jpg", 43, 47, 15, 90, datetime(2026, 1, 1))

    def test_panorama_markers_support_tuple_aggregate_and_release_connection(self):
        self.insert_pano()
        for query in ["", "?north=44&south=42&west=46&east=48&zoom=18", "?north=44&south=42&west=46&east=48&zoom=10"]:
            response = self.client.get("/api/panoramas" + query)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            markers = response.get_json()
            self.assertEqual(len(markers), 1)
            self.assertEqual(markers[0]["count"], 1)
            self.assertAlmostEqual(markers[0]["lat"], 43)
            self.assert_released()

    def test_metadata_missing_row_and_download_do_not_hold_db_connection(self):
        self.insert_pano()
        response = self.client.get("/api/pano_info/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filename"], "test.jpg")
        self.assertEqual(self.client.get("/api/pano_info/99999").status_code, 404)
        # The storage probe asserts that every connection is closed before it runs.
        self.assertEqual(self.client.get("/api/pano_info/1/download").status_code, 200)
        self.assert_released()

    def test_delete_commits_before_object_storage_and_closes_for_missing_row(self):
        self.insert_pano()
        self.assertEqual(self.client.delete("/api/pano_info/1").status_code, 200)
        self.assertEqual(self.controller.storage.deleted, ["test.jpg"])
        self.assertEqual(self.client.delete("/api/pano_info/1").status_code, 404)
        self.assert_released()

    def test_ortho_crud_preserves_footprint_and_releases_every_operation(self):
        record = Ortho("scope.tif", crs="EPSG:4326", is_cog=True,
                       geometry_wkt="POLYGON((47 43,48 43,48 42,47 42,47 43))")
        ortho_id = self.orthos.insert_ortho(record)
        self.assert_released()
        self.orthos.update_ortho(ortho_id, {"is_visible": True})
        restored = self.orthos.get_ortho_by_id(ortho_id)
        self.assertTrue(restored.is_visible)
        self.assertEqual(restored.wgs84_bounds, {"west": 47, "east": 48, "south": 42, "north": 43})
        self.assertEqual(len(self.orthos.get_all_orthos()), 1)
        self.orthos.delete_ortho(ortho_id)
        self.assertIsNone(self.orthos.get_ortho_by_id(ortho_id))
        self.assert_released()

    def test_panorama_coordinate_update_uses_one_transaction(self):
        self.insert_pano()
        self.db.connections.clear()
        self.panos.update_pano(1, {"latitude": 43.5})
        self.assertEqual(len(self.db.connections), 1)
        self.assert_released()
        with self.db.cursor() as cursor:
            cursor.execute("SELECT latitude, ST_Y(geom) AS y FROM public.photos_4326 WHERE id=1")
            row = cursor.fetchone()
        self.assertEqual(row["latitude"], "43.5")
        self.assertEqual(row["y"], 43.5)

    def test_vector_layer_creation_is_atomic_when_postgis_rejects_geometry_type(self):
        name = "invalid_" + uuid4().hex
        response = self.client.post("/api/vector/layers/create", json={
            "dbName": self.db_name, "schema": "public", "tableName": name, "geomType": "INVALID_GEOMETRY",
        })
        self.assertEqual(response.status_code, 500)
        with self.db.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s) AS relation", (f"public.{name}",))
            self.assertIsNone(cursor.fetchone()["relation"])
        self.assert_released()

    def test_vector_tiles_and_geojson_use_same_dsn_and_release_connections(self):
        name = "valid_" + uuid4().hex
        response = self.client.post("/api/vector/layers/create", json={
            "dbName": self.db_name, "schema": "public", "tableName": name, "geomType": "POINT",
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        try:
            with self.db.cursor(write=True) as cursor:
                cursor.execute(sql.SQL("INSERT INTO public.{} (geom) VALUES (ST_SetSRID(ST_MakePoint(47,43),4326))").format(sql.Identifier(name)))
            for path in [f"/api/vector/layers/{self.db_name}/{name}/data",
                         f"/api/vector/tiles/{self.db_name}/public/{name}/0/0/0.pbf",
                         f"/api/vector/tiles/combined/{self.db_name}/0/0/0.pbf?layers={name}&schema=public"]:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.get_data())
                self.assertTrue(response.get_data())
                self.assert_released()
        finally:
            with self.db.cursor(write=True) as cursor:
                cursor.execute(sql.SQL("DROP TABLE public.{}").format(sql.Identifier(name)))

    def test_administrative_connection_is_explicitly_autocommit_and_released(self):
        connection = vector.get_db_connection(self.db_name, autocommit=True)
        self.assertIsNotNone(connection)
        try:
            self.assertTrue(connection.autocommit)
            self.assertEqual(connection.info.dbname, self.db_name)
        finally:
            vector.release_db_connection(connection)
        self.assert_released()

    def test_real_application_login_and_routes_release_database_transactions(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("application_database_probe.py"))],
                                env=os.environ.copy(), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("application transaction smoke passed", result.stdout)

    def test_concurrent_legacy_schema_initialization_is_serialized(self):
        with self.db.cursor(write=True) as cursor:
            cursor.execute("DROP TABLE orthophotos")
        gate = threading.Barrier(2)
        errors = []

        def initialize():
            try:
                gate.wait(timeout=5)
                OrthoManager(self.db)
            except BaseException as error:
                errors.append(repr(error))

        workers = [threading.Thread(target=initialize) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertEqual(self.orthos.get_all_orthos(), [])
        self.assert_released()

