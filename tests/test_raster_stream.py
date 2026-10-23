import json
from pathlib import Path
import sys
import threading
import unittest
from flask import Flask
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from raster_stream import tile_stream

class RasterStreamTests(unittest.TestCase):
    def test_fast_tile_is_yielded_while_other_tile_is_still_rendering(self):
        release=threading.Event();started=threading.Event()
        self.addCleanup(release.set)
        class Service:
            def proxy_tile(self,identifier,z,x,y,**kwargs):
                if x==0:started.set();release.wait(timeout=5)
                return b'webp-fixture'
        app=Flask(__name__)
        app.add_url_rule('/tiles',view_func=lambda:tile_stream(Service(),1))
        response=app.test_client().get('/tiles?z=1&tiles=0,0;1,0',buffered=False)
        try:
            row=json.loads(next(iter(response.response)))
            self.assertEqual(row['x'],1);self.assertTrue(started.wait(timeout=1));self.assertFalse(release.is_set())
        finally:release.set();response.close()
