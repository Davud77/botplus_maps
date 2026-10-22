import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from psycopg2.extras import Json
from PIL import Image
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
                self.assertEqual(pano.read_bytes(),before)
                self.assertEqual(len(list(managed.rglob('*.jpg'))),0)
                outside=Path(folder)/'outside.jpg';outside.write_bytes(before);(root/'escape.jpg').symlink_to(outside)
                with self.assertRaises(ValueError):worker.source_path('test','escape.jpg')
                with self.assertRaises(ValueError):worker.source_path('test','../outside.jpg')
            with db.cursor(write=True) as cur:
                cur.execute("DELETE FROM public.photos_4326 WHERE filename LIKE '%sphere.jpg'");cur.execute("DELETE FROM media_import_jobs WHERE source->>'root_id'='test'")
