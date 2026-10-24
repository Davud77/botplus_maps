import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from psycopg2.extras import Json
from PIL import Image
from flask import Flask
import piexif
from server.database import Database
from server.controllers.pano_controller import PanoController
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import media_worker as worker


@unittest.skipUnless(os.environ.get('TEST_POSTGIS')=='1','Requires disposable PostGIS')
class MediaWorkerTests(unittest.TestCase):
    def test_nas_import_only_360_is_idempotent_and_original_stays_unchanged(self):
        db=Database(os.environ['TEST_DATABASE_URL']);c=PanoController.__new__(PanoController);c.db=db;c._ensure_table()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source';root.mkdir();managed=Path(folder)/'managed';managed.mkdir()
            exif=piexif.dump({'GPS':{piexif.GPSIFD.GPSLatitudeRef:b'N',piexif.GPSIFD.GPSLatitude:((43,1),(0,1),(0,1)),piexif.GPSIFD.GPSLongitudeRef:b'E',piexif.GPSIFD.GPSLongitude:((47,1),(0,1),(0,1))}})
            pano=root/'sphere.jpg';photo=root/'photo.jpg';Image.new('RGB',(1024,512),'blue').save(pano,exif=exif);Image.new('RGB',(40,30),'red').save(photo,exif=exif);before=pano.read_bytes()
            with patch.dict(os.environ,{'LOCAL_SOURCE_ROOTS':'{"test":"'+str(root)+'"}'}),patch.object(worker.config,'MEDIA_ROOT',str(managed)):
                for attempt in range(2):
                    identifier=str(uuid4())
                    with db.cursor(write=True) as cur:cur.execute('INSERT INTO media_import_jobs(id,owner_id,source) VALUES (%s,1,%s)',(identifier,Json({'root_id':'test','key':'.','only_360':True})))
                    # Claim this test's job without depending on other test fixtures.
                    with db.cursor(write=True) as cur:
                        cur.execute("UPDATE media_import_jobs SET status='running',lease_token=%s,lease_until=NOW()+INTERVAL '90 seconds' WHERE id=%s RETURNING *",(str(uuid4()),identifier));job=cur.fetchone()
                    worker.execute(job,db)
                    with db.cursor() as cur:
                        cur.execute('SELECT * FROM media_import_jobs WHERE id=%s',(identifier,));result=cur.fetchone()
                    self.assertEqual(result['status'],'succeeded');self.assertEqual(result['failed'],0);self.assertEqual(result['imported'],1 if attempt==0 else 0)
                # NAS references must serve the original bytes, including Range,
                # and refuse changed sources without converting a 409 into 500.
                with db.cursor() as cur:
                    cur.execute("SELECT id FROM public.photos_4326 WHERE source_ref->>'root_id'='test' AND source_ref->>'key'='sphere.jpg'");photo_id=cur.fetchone()['id']
                app=Flask(__name__)
                app.add_url_rule('/info/<int:pano_id>',view_func=c.get_pano_info)
                app.add_url_rule('/download/<int:pano_id>',view_func=c.download_pano_file)
                client=app.test_client()
                self.assertEqual(client.get(f'/info/{photo_id}').json['media_type'],'panorama')
                response=client.get(f'/download/{photo_id}',headers={'Range':'bytes=0-15'})
                self.assertEqual(response.status_code,206);self.assertEqual(response.data,before[:16]);response.close()
                pano.write_bytes(before+b'changed')
                self.assertEqual(client.get(f'/info/{photo_id}').status_code,409)
                self.assertEqual(client.get(f'/download/{photo_id}').status_code,409)
                pano.write_bytes(before)
                self.assertEqual(pano.read_bytes(),before)
                self.assertEqual(len(list(managed.rglob('*.jpg'))),0)
                outside=Path(folder)/'outside.jpg';outside.write_bytes(before);(root/'escape.jpg').symlink_to(outside)
                with self.assertRaises(ValueError):worker.source_path('test','escape.jpg')
                with self.assertRaises(ValueError):worker.source_path('test','../outside.jpg')
            with db.cursor(write=True) as cur:
                cur.execute("DELETE FROM public.photos_4326 WHERE filename LIKE '%sphere.jpg'");cur.execute("DELETE FROM media_import_jobs WHERE source->>'root_id'='test'")

    def test_web_panorama_upload_only_enqueues_then_worker_reads_metadata(self):
        from io import BytesIO
        from flask import g
        from server import config as controller_config
        db=Database(os.environ['TEST_DATABASE_URL'])
        controller=PanoController.__new__(PanoController);controller.db=db;controller._ensure_table()
        app=Flask(__name__)
        @app.before_request
        def identify():g.current_user_id=1
        app.add_url_rule('/upload',view_func=controller.upload_pano_files,methods=['POST'])
        with tempfile.TemporaryDirectory() as folder:
            stream=BytesIO()
            exif=piexif.dump({'GPS':{piexif.GPSIFD.GPSLatitudeRef:b'N',piexif.GPSIFD.GPSLatitude:((43,1),(0,1),(0,1)),piexif.GPSIFD.GPSLongitudeRef:b'E',piexif.GPSIFD.GPSLongitude:((47,1),(0,1),(0,1))}})
            Image.new('RGB',(1024,512),'blue').save(stream,format='JPEG',exif=exif);stream.seek(0)
            with patch.object(controller_config,'MEDIA_ROOT',folder),patch.object(worker.config,'MEDIA_ROOT',folder):
                response=app.test_client().post('/upload',data={'files':(stream,'queued-sphere.jpg'),'only_360':'true','tags':'survey'},content_type='multipart/form-data')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['successful_uploads'],['queued-sphere.jpg'])
                with db.cursor(write=True) as cur:
                    cur.execute("SELECT * FROM media_import_jobs WHERE source->>'title'='queued-sphere.jpg' ORDER BY created_at DESC LIMIT 1")
                    queued=cur.fetchone();self.assertEqual(queued['status'],'queued');self.assertEqual(queued['processed'],0)
                    cur.execute("UPDATE media_import_jobs SET status='running',lease_token=%s,lease_until=NOW()+INTERVAL '90 seconds' WHERE id=%s RETURNING *",(str(uuid4()),str(queued['id'])))
                    job=cur.fetchone()
                worker.execute(job,db)
                with db.cursor() as cur:
                    cur.execute('SELECT status,imported,total FROM media_import_jobs WHERE id=%s',(str(queued['id']),));result=cur.fetchone()
                    self.assertEqual(result['status'],'succeeded');self.assertEqual(result['imported'],1);self.assertEqual(result['total'],1)
                    cur.execute("SELECT tags FROM public.photos_4326 WHERE source_ref->>'key'=%s",(job['source']['key'],));self.assertEqual(cur.fetchone()['tags'],'survey')
                with db.cursor(write=True) as cur:
                    cur.execute("DELETE FROM public.photos_4326 WHERE source_ref->>'key'=%s",(job['source']['key'],))
                    cur.execute('DELETE FROM media_import_jobs WHERE id=%s',(str(queued['id']),))
