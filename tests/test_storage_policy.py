"""Managed NAS files: isolation, atomic publication, streaming and HTTP ranges."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from server.storage import FileStorage
from scripts.migrate_minio import migrate


class BoundedStream(io.BytesIO):
    def read(self, size=-1):
        if not 0 < size <= 1024 * 1024:
            raise AssertionError('Unbounded file read')
        return super().read(size)


class FileStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = FileStorage(Path(self.directory.name) / 'media')

    def test_rejects_paths_and_symlinks_outside_namespace(self):
        for key in ['../secret', '/etc/passwd', 'a/../../secret', 'a\\secret', 'C:/secret', '', 'a//b', './a']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.store.path(key)
        (self.store.root / 'link').symlink_to(self.directory.name, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.store.save_file(io.BytesIO(b'bad'), 'link/secret')

    def test_streams_sharded_files_and_never_overwrites_same_key(self):
        data = b'x' * (3 * 1024 * 1024 + 7)
        self.store.save_file(BoundedStream(data), 'ab/cd/pano.jpg')
        self.assertEqual((self.store.root / 'ab/cd/pano.jpg').read_bytes(), data)
        with self.assertRaises(FileExistsError):
            self.store.save_file(io.BytesIO(b'replacement'), 'ab/cd/pano.jpg')
        self.assertEqual((self.store.root / 'ab/cd/pano.jpg').stat().st_size, len(data))
        self.assertFalse(list(self.store.root.rglob('.upload-*')))

    def test_failed_copy_never_publishes_partial_file(self):
        with patch('server.storage.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.store.save_file(io.BytesIO(b'data'), 'partial.tif')
        self.assertFalse(list(self.store.root.iterdir()))

    def test_streamed_download_supports_ranges_and_missing_files(self):
        self.store.save_file(io.BytesIO(b'0123456789'), 'ab/photo.jpg')
        app = Flask(__name__)
        app.add_url_rule('/files/<path:key>', view_func=lambda key: self.store.send_local_file(key))
        client = app.test_client()
        with client.get('/files/ab/photo.jpg', headers={'Range': 'bytes=2-5'}) as response:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.data, b'2345')
            self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
        self.assertEqual(client.get('/files/missing.jpg').status_code, 404)

    def test_namespaces_are_independent_and_delete_cannot_touch_source(self):
        source = Path(self.directory.name) / 'original.tif'
        source.write_bytes(b'original')
        other = FileStorage(Path(self.directory.name) / 'other')
        self.store.save_file(io.BytesIO(b'pano'), 'same.jpg')
        other.save_file(io.BytesIO(b'ortho'), 'same.jpg')
        self.store.delete_file('same.jpg')
        self.assertEqual(other.path('same.jpg').read_bytes(), b'ortho')
        self.assertEqual(source.read_bytes(), b'original')

    def test_migration_is_verified_repeatable_and_preserves_source(self):
        from types import SimpleNamespace
        class Response(BoundedStream):
            def release_conn(self): pass
        class Client:
            def bucket_exists(self, bucket): return bucket == 'panoramas'
            def list_objects(self, *args, **kwargs):
                return [SimpleNamespace(object_name='ab/pano.jpg', size=4)]
            def get_object(self, *args): return Response(b'pano')
        client = Client()
        self.assertEqual(migrate(client, self.store.root)['copied'], 0)
        first = migrate(client, self.store.root, apply=True)
        self.assertEqual((first['copied'], first['verified']), (1, 1))
        second = migrate(client, self.store.root, apply=True)
        self.assertEqual((second['copied'], second['verified']), (0, 1))
        target = self.store.root / 'panoramas/ab/pano.jpg'
        target.write_bytes(b'other')
        with self.assertRaises(ValueError):
            migrate(client, self.store.root, apply=True)
        self.assertEqual(target.read_bytes(), b'other')
