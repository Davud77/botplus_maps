"""Separate bounded-memory raster worker: python server/job_worker.py."""
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import threading
import uuid
from psycopg2.extras import Json
from database import Database
import import_jobs as jobs
from geo.raster import inspect_raster

log=logging.getLogger(__name__)
STOP=threading.Event()


class LeaseLost(Exception): pass


class Lease:
    def __init__(self,job,db,*,table='import_jobs',event_writer=None):
        if table not in {'import_jobs','raster_display_jobs'}:raise ValueError('Invalid job table')
        self.table=table;self.event_writer=event_writer or jobs.event
        self.job=job;self.db=db;self.done=threading.Event();self.lost=threading.Event()
        self.thread=threading.Thread(target=self.heartbeat,daemon=True)
    def heartbeat(self):
        while not self.done.wait(5):
            try:
                with self.db.cursor(write=True) as cur:
                    cur.execute(f"""UPDATE {self.table} SET lease_until=NOW()+make_interval(secs=>%s),updated_at=NOW()
                        WHERE id=%s AND lease_token=%s AND status='running' AND lease_until>NOW() AND NOT cancel_requested RETURNING id""",
                        (jobs.LEASE_SECONDS,str(self.job['id']),str(self.job['lease_token'])))
                    if not cur.fetchone(): self.lost.set();return
            except Exception: self.lost.set();return
    def check(self):
        if STOP.is_set() or self.lost.is_set(): raise LeaseLost('Обработка прервана; исходник сохранён.')
        with self.db.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {self.table} WHERE id=%s AND lease_token=%s AND status='running' AND lease_until>NOW() AND NOT cancel_requested",(str(self.job['id']),str(self.job['lease_token'])))
            if not cur.fetchone(): raise LeaseLost('Обработка отменена или worker потерял аренду задания.')
    def progress(self,percent,message,*,record=False):
        self.check()
        with self.db.cursor(write=True) as cur:
            cur.execute(f"UPDATE {self.table} SET progress=%s,message=%s,updated_at=NOW() WHERE id=%s AND lease_token=%s AND status='running'",(percent,message,str(self.job['id']),str(self.job['lease_token'])))
            if record:self.event_writer(cur,self.job['id'],message)


def execute(job,db=None):
    db=db or Database();lease=Lease(job,db);lease.thread.start()
    product=None;keep_product=False
    try:
        source=job['source'];original=jobs.resolve_source(source['root_id'],source['key'],internal=True)
        if jobs.fingerprint(original)!=source['fingerprint']: raise ValueError('Файл изменился после постановки в очередь. Создайте новый импорт.')
        lease.progress(5,'Проверка GeoTIFF и системы координат',record=True)
        report=inspect_raster(original,source_crs=source['source_crs'])
        ready=report['cog_layout_hint'] and not source['source_crs'] and (max(report['width'],report['height'])<=512 or all(band['overviews'] for band in report['bands']))
        asset={'source':source,'kind':'source'}
        if not ready:
            from osgeo import gdal
            gdal.SetCacheMax(128*1024*1024)
            folder=jobs.products_root()/str(job['id'])/str(job['lease_token']);folder.mkdir(parents=True,exist_ok=True)
            product=folder/'raster.tif'
            # Conservative preflight; compression, scratch and overviews vary.
            raw_bytes=report['width']*report['height']*sum(max(1,(gdal.GetDataTypeSize(gdal.GetDataTypeByName(band['data_type']))+7)//8) for band in report['bands'])
            if shutil.disk_usage(folder).free < max(raw_bytes*3,report['size_bytes']*3)+256*1024*1024:
                raise ValueError('Недостаточно свободного места для COG и временных файлов. Подготовьте COG отдельно или освободите рабочий диск.')
            lease.progress(10,'Подготовка отдельного COG; оригинал сохраняется',record=True)
            last=[-1]
            def progress(fraction,message,data):
                if STOP.is_set() or lease.lost.is_set(): return 0
                percent=10+int(fraction*75)
                if percent//5!=last[0]:
                    try: lease.progress(percent,'Подготовка COG');last[0]=percent//5
                    except Exception: return 0
                return 1
            options={'format':'COG','creationOptions':['COMPRESS=DEFLATE','BIGTIFF=IF_SAFER','BLOCKSIZE=512','NUM_THREADS=2','OVERVIEWS=AUTO'],'callback':progress}
            if source['source_crs']: options['outputSRS']=source['source_crs']
            result=gdal.Translate(str(product),str(original),options=gdal.TranslateOptions(**options))
            if result is None: raise RuntimeError('GDAL не завершил подготовку COG.')
            result=None
            report=inspect_raster(product)
            if not report['cog_layout_hint']: raise RuntimeError('Подготовленный файл не имеет COG layout.')
            asset.update(kind='product',key=str(product.relative_to(jobs.products_root())),fingerprint=jobs.fingerprint(product))
        lease.progress(90,'Регистрация в каталоге',record=True)
        if jobs.fingerprint(original)!=source['fingerprint']: raise ValueError('Исходный файл изменился во время обработки.')
        with db.cursor(write=True) as cur:
            cur.execute("SELECT 1 FROM import_jobs WHERE id=%s AND lease_token=%s AND status='running' AND lease_until>NOW() AND NOT cancel_requested FOR UPDATE",(str(job['id']),str(job['lease_token'])))
            if not cur.fetchone(): raise LeaseLost('Задание отменено или аренда завершена.')
            # Serialize only the short publication transaction, never GDAL work.
            cur.execute('SELECT pg_advisory_xact_lock(%s)',(941027003,))
            cur.execute('SELECT ortho_id FROM import_assets WHERE signature=%s',(source['signature'],));existing=cur.fetchone()
            if existing: ortho_id=existing['ortho_id']
            else:
                crs=f"{report['crs_authority']}:{report['crs_code']}" if report['crs_authority'] and report['crs_code'] else report['crs_wkt']
                cur.execute('''INSERT INTO orthophotos (filename,bounds,crs,is_visible,is_cog,geometry)
                    VALUES (%s,%s,%s,TRUE,TRUE,ST_Multi(ST_GeomFromText(%s,4326))) RETURNING id''',
                    (source['title'],json.dumps(report['native_bounds']),crs,report['footprint_wkt']))
                ortho_id=cur.fetchone()['id']
                cur.execute('INSERT INTO import_assets (ortho_id,job_id,signature,asset) VALUES (%s,%s,%s,%s)',(ortho_id,str(job['id']),source['signature'],Json(asset)))
                keep_product=product is not None
            result={'ortho_id':ortho_id,'no_copy':ready,'width':report['width'],'height':report['height'],'size_bytes':report['size_bytes'],'validation':'metadata_only'}
            cur.execute("UPDATE import_jobs SET status='succeeded',progress=100,message='Слой добавлен в каталог',result=%s,lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s",(Json(result),str(job['id'])))
            jobs.event(cur,job['id'],'Слой добавлен в каталог без изменения оригинала.')
        return result
    except Exception as exc:
        log.exception('Import job %s failed',job['id'])
        message=str(exc)
        for path in list(jobs.roots().values())+[jobs.products_root(),jobs.staging_root()]: message=message.replace(str(path),'[источник]')
        with db.cursor(write=True) as cur:
            cur.execute("""UPDATE import_jobs SET status=CASE WHEN cancel_requested THEN 'cancelled' WHEN %s THEN 'queued' ELSE 'failed' END,
                attempts=CASE WHEN %s THEN greatest(0,attempts-1) ELSE attempts END,error=%s,message='Обработка остановлена; оригинал сохранён',lease_token=NULL,lease_until=NULL,updated_at=NOW()
                WHERE id=%s AND lease_token=%s AND status='running' RETURNING id""",(STOP.is_set(),STOP.is_set(),message[:1000],str(job['id']),str(job['lease_token'])))
            if cur.fetchone(): jobs.event(cur,job['id'],message[:1000])
        return None
    finally:
        lease.done.set();lease.thread.join(timeout=2)
        if product and not keep_product: product.unlink(missing_ok=True)


def main():
    logging.basicConfig(level=logging.INFO)
    jobs.roots()
    signal.signal(signal.SIGTERM,lambda *args:STOP.set())
    signal.signal(signal.SIGINT,lambda *args:STOP.set())
    while not STOP.is_set():
        try:
            job=jobs.claim()
            if job: execute(job)
            else: STOP.wait(2)
        except Exception:
            log.exception('Worker database unavailable');STOP.wait(5)


if __name__=='__main__': main()
