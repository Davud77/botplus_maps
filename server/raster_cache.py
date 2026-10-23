"""Disposable PNG tiles on NAS, bounded per shard; no SQLite or source copies.

Every caller validates source fingerprints before looking up a key. A shard lock
coalesces misses across threads/processes. Reserve the FIFO index before publishing
bytes so a crash cannot create an unaccounted final tile. Atomic renames prevent
partial responses. Neither errors nor invalid PNGs are cached.
"""
from collections import OrderedDict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
from storage import FileStorage

PNG=b'\x89PNG\r\n\x1a\n'


class RasterCache:
    def __init__(self,root,memory_bytes=32*1024**2,shard_bytes=64*1024**2,shard_entries=128,ttl=86400):
        self.storage=FileStorage(root);self.memory_limit=memory_bytes;self.shard_bytes=shard_bytes;self.shard_entries=shard_entries;self.ttl=ttl
        self.memory=OrderedDict();self.used=0;self.mutex=threading.Lock()

    @staticmethod
    def key(asset,z,x,y,scale):
        return hashlib.sha256(json.dumps({'recipe':'png-v1','asset':asset,'tile':[z,x,y,scale],'rescale':'0,255'},sort_keys=True,default=str).encode()).hexdigest()

    def remember(self,key,value):
        if len(value)>self.memory_limit:return
        with self.mutex:
            old=self.memory.pop(key,None)
            if old:self.used-=len(old[1])
            self.memory[key]=(time.time(),value);self.used+=len(value)
            while self.used>self.memory_limit:
                _,(_,removed)=self.memory.popitem(last=False);self.used-=len(removed)

    @staticmethod
    def valid(value):
        return len(value)>=45 and value.endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82') and value.startswith(PNG) and struct.unpack('>II',value[16:24]) in {(256,256),(512,512)}

    def publish(self,path,value):
        descriptor,temporary=tempfile.mkstemp(prefix='.tile-',dir=path.parent)
        try:
            with os.fdopen(descriptor,'wb') as stream:stream.write(value)
            os.replace(temporary,path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def get(self,key,render):
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid cache key')
        now=time.time()
        with self.mutex:
            item=self.memory.get(key)
            if item and now-item[0]<self.ttl:
                self.memory.move_to_end(key);return item[1],'MEMORY'
            if item:self.used-=len(item[1]);del self.memory[key]
        prefix=key[:2];folder=self.storage.path(prefix);folder.mkdir(exist_ok=True)
        path=self.storage.path(prefix+'/'+key+'.png')
        def read():
            try:
                info=path.stat()
                if now-info.st_mtime>=self.ttl or info.st_size>8*1024**2:return None
                value=path.read_bytes()
                return value if self.valid(value) else None
            except OSError:return None
        value=read()
        if value is not None:self.remember(key,value);return value,'DISK'
        lock_path=self.storage.path(prefix+'/_lock')
        descriptor=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            deadline=time.monotonic()+40
            while True:
                try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>deadline:raise TimeoutError('Tile cache busy')
                    time.sleep(.025)
            value=read()
            if value is not None:self.remember(key,value);return value,'DISK'
            value=render()
            if value is None or not self.valid(value):return value,'BYPASS'
            index_path=self.storage.path(prefix+'/_index.json')
            try:
                if index_path.stat().st_size>256*1024:raise ValueError()
                index=json.loads(index_path.read_text())
                if not isinstance(index,dict) or any(not isinstance(v,dict) or set(v)!={'size','at'} or type(v['size']) is not int or v['size']<0 or not isinstance(v['at'],(int,float)) or len(k)!=64 or not all(c in '0123456789abcdef' for c in k) for k,v in index.items()):raise ValueError()
            except (OSError,ValueError,TypeError):
                # Recover only this bounded shard after an interrupted first write.
                index={}
                for candidate in folder.glob('*.png'):
                    if len(candidate.stem)==64 and all(c in '0123456789abcdef' for c in candidate.stem):
                        st=candidate.stat();index[candidate.stem]={'size':st.st_size,'at':st.st_mtime}
            index.pop(key,None)
            for old in list(index):
                if now-index[old]['at']>=self.ttl:
                    self.storage.path(prefix+'/'+old+'.png').unlink(missing_ok=True);del index[old]
            while index and (len(index)>=self.shard_entries or sum(i['size'] for i in index.values())+len(value)>self.shard_bytes):
                old=min(index,key=lambda k:index[k]['at']);self.storage.path(prefix+'/'+old+'.png').unlink(missing_ok=True);del index[old]
            try:
                if len(value)<=self.shard_bytes and self.shard_entries>0:
                    index[key]={'size':len(value),'at':now}
                    self.publish(index_path,json.dumps(index).encode())
                    self.publish(path,value)
            except OSError:
                self.remember(key,value);return value,'BYPASS'
            self.remember(key,value);return value,'MISS'
        finally:
            fcntl.flock(descriptor,fcntl.LOCK_UN);os.close(descriptor)


_instances={};_instances_lock=threading.Lock()
def configured_cache():
    import config
    root=os.getenv('RASTER_TILE_CACHE_DIR',str(Path(config.MEDIA_ROOT).parent/'cache'/'raster'))
    with _instances_lock:
        if root not in _instances:
            memory=max(0,int(os.getenv('RASTER_CACHE_MEMORY_MB','32')))*1024**2
            disk=max(0,int(os.getenv('RASTER_CACHE_DISK_MB','16384')))*1024**2//256
            entries=max(0,int(os.getenv('RASTER_CACHE_ENTRIES','32768')))//256
            ttl=max(1,int(os.getenv('RASTER_CACHE_TTL_SECONDS','86400')))
            _instances[root]=RasterCache(root,memory_bytes=memory,shard_bytes=disk,shard_entries=entries,ttl=ttl)
        return _instances[root]
