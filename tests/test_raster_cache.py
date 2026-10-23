import concurrent.futures
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from raster_cache import RasterCache,PNG


def png(scale=1):
    def chunk(kind,content):return struct.pack('>I',len(content))+kind+content+struct.pack('>I',zlib.crc32(kind+content)&0xffffffff)
    size=256*scale
    return PNG+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x30\x80\x40\xff'*size)*size))+chunk(b'IEND',b'')


class RasterCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.image=png();self.key='aa'+'0'*62
    def test_memory_and_disk_hits_preserve_exact_png_bytes(self):
        cache=RasterCache(self.root);calls=[]
        def render():calls.append(1);return self.image
        self.assertEqual(cache.get(self.key,render),(self.image,'MISS'))
        self.assertEqual(cache.get(self.key,render),(self.image,'MEMORY'))
        self.assertEqual(RasterCache(self.root).get(self.key,render),(self.image,'DISK'));self.assertEqual(len(calls),1)
    def test_threads_and_independent_instances_coalesce_one_render(self):
        calls=[];lock=threading.Lock()
        def render():
            with lock:calls.append(1)
            time.sleep(.05);return self.image
        def fetch(_):return RasterCache(self.root).get(self.key,render)[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:results=list(workers.map(fetch,range(8)))
        self.assertTrue(all(v==self.image for v in results));self.assertEqual(len(calls),1)
    def test_failed_or_partial_png_is_not_persisted(self):
        cache=RasterCache(self.root)
        for invalid in [None,b'error',self.image[:24]]:
            self.assertEqual(cache.get(self.key,lambda:invalid),(invalid,'BYPASS'))
            self.assertFalse(list(self.root.rglob('*.png')))
        self.assertEqual(cache.get(self.key,lambda:self.image)[1],'MISS')
    def test_fifo_quota_and_ttl_bound_persistent_cache(self):
        cache=RasterCache(self.root,memory_bytes=0,shard_entries=1)
        cache.get(self.key,lambda:self.image);other='aa'+'1'*62;cache.get(other,lambda:self.image)
        self.assertFalse((self.root/'aa'/(self.key+'.png')).exists());self.assertEqual(len(list(self.root.rglob('*.png'))),1)
        path=self.root/'aa'/(other+'.png');os.utime(path,(0,0))
        self.assertEqual(cache.get(other,lambda:self.image)[1],'MISS')
        index=json.loads((self.root/'aa'/'_index.json').read_text());self.assertEqual(len(index),1)
    def test_versions_and_scale_have_independent_cache_keys(self):
        a={'source':{'fingerprint':{'st_mtime_ns':1}}};b={'source':{'fingerprint':{'st_mtime_ns':2}}}
        self.assertNotEqual(RasterCache.key(a,10,1,2,1),RasterCache.key(b,10,1,2,1))
        self.assertNotEqual(RasterCache.key(a,10,1,2,1),RasterCache.key(a,10,1,2,2));self.assertTrue(RasterCache.valid(png(2)))
    def test_cache_publication_failure_does_not_render_twice(self):
        cache=RasterCache(self.root);calls=[]
        def fail(*_):raise OSError('NAS full')
        cache.publish=fail
        def render():calls.append(1);return self.image
        self.assertEqual(cache.get(self.key,render),(self.image,'BYPASS'));self.assertEqual(len(calls),1)
