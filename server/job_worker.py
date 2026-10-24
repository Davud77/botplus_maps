"""Separate bounded-memory raster worker: python server/job_worker.py."""
import json
import sys
sys.modules.setdefault("job_worker",sys.modules[__name__])
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
        source=job['source']
        if source.get('operation'):
            return execute_operation(job,db,lease)
        original=jobs.resolve_source(source['root_id'],source['key'],internal=True)
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
                from services.map_settings import ensure_projection
                definition=f"{report['crs_authority']}:{report['crs_code']}" if report['crs_authority'] and report['crs_code'] else report['crs_wkt']
                crs=ensure_projection(cur,definition)['id']
                cur.execute('''INSERT INTO orthophotos (filename,bounds,crs,is_visible,is_cog,geometry)
                    VALUES (%s,%s,%s,TRUE,TRUE,ST_Multi(ST_GeomFromText(%s,4326))) RETURNING id''',
                    (source['title'],json.dumps(report['native_bounds']),crs,report['footprint_wkt']))
                ortho_id=cur.fetchone()['id']
                cur.execute('INSERT INTO import_assets (ortho_id,job_id,signature,asset) VALUES (%s,%s,%s,%s)',(ortho_id,str(job['id']),source['signature'],Json(asset)))
                keep_product=product is not None
            result={'ortho_id':ortho_id,'no_copy':ready,'width':report['width'],'height':report['height'],'size_bytes':report['size_bytes'],'validation':'metadata_only'}
            jobs.event(cur,job['id'],'Слой добавлен в каталог без изменения оригинала.')
        lease.progress(95,'Автоматическое создание превью',record=True)
        from controllers.data_import import create_preview
        create_preview(ortho_id,product or original,db)
        lease.check()
        with db.cursor(write=True) as cur:
            cur.execute("UPDATE import_jobs SET status='succeeded',progress=100,message='Слой добавлен в каталог',result=%s,lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s AND lease_token=%s AND NOT cancel_requested",(Json(result),str(job['id']),str(job['lease_token'])))
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


def execute_operation(job,db,lease):
    source=job['source'];payload=source['payload'];operation=source['operation']
    lease.progress(1,'Начато выполнение',record=True)
    if operation=='panorama-coverage':
        from services.panorama_coverage import rebuild
        result=rebuild(db,lease)
    elif operation=='register-folder':
        result=execute_raster_folder(payload,db,lease)
    elif operation=='register':
        from controllers.data_import import register
        result=register(payload['root_id'],payload['key'],payload.get('title',''),db,lease=lease)
    else:
        from managers.ortho_manager import OrthoManager
        from services.ortho_service import OrthoService
        from services.storage_service import StorageService
        from services.gdal_service import GdalService
        service=OrthoService(db,OrthoManager(db),StorageService(),GdalService(),None)
        service.temp_dir=str(Path(service.temp_dir)/str(job['id']))
        Path(service.temp_dir).mkdir(parents=True,exist_ok=True)
        service.worker_task_id=str(job['id'])
        class Progress:
            def save_state(self,task_id,state):
                if state.get('status')=='error':raise RuntimeError(state.get('error','Ошибка обработки'))
                lease.progress(min(99,state.get('progress',0)),state.get('message','Обработка'),record=True)
        service.tasks=Progress()
        if operation=='reproject':
            task_id=service.start_reproject_process(payload['ortho_id'],payload.get('target_crs','EPSG:3857'))
        else:task_id=getattr(service,{'cog':'start_cog_process','reproject':'start_reproject_process','preview':'start_preview_process'}[operation])(payload['ortho_id'])
        if not task_id:raise ValueError('Ортофотоплан удалён до начала задания.')
        result={'ortho_id':payload['ortho_id']}
    lease.check()
    with db.cursor(write=True) as cur:
        cur.execute("""UPDATE import_jobs SET status='succeeded',progress=100,message=%s,result=%s,
            lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s AND lease_token=%s AND NOT cancel_requested RETURNING id""",
            ('Завершено с ошибками' if result.get('failed') else 'Задание завершено',Json(result),str(job['id']),str(job['lease_token'])))
        if not cur.fetchone():raise LeaseLost('Задание отменено')
        jobs.event(cur,job['id'],'Задание завершено: '+source['title'])
    return result


def execute_raster_folder(payload,db,lease):
    from controllers.data_import import register,raster_files
    from media_worker import source_path
    root,folder=source_path(payload['root_id'],payload['key'])
    if not folder.is_dir():raise ValueError('Папка ортофотопланов недоступна.')
    total=0
    for _ in raster_files(folder):
        lease.check();total+=1
    if not total:raise ValueError('В папке нет GeoTIFF.')
    completed=0;imported=0;failed=0
    class FileProgress:
        job=lease.job
        def progress(self,percent,message,*,record=False):
            lease.progress(min(99,int((completed+percent/100)*100/total)),f'{completed+1}/{total}: {message}',record=record)
    progress=FileProgress()
    for path in raster_files(folder):
        lease.check()
        try:
            register(payload['root_id'],str(path.relative_to(root)),db=db,lease=progress)
            imported+=1
        except LeaseLost:raise
        except Exception as exc:
            lease.check();failed+=1
            lease.progress(min(99,int((completed+1)*100/total)),f'{path.name}: {type(exc).__name__}',record=True)
        completed+=1
    return {'processed':completed,'imported':imported,'failed':failed}


def main():
    logging.basicConfig(level=logging.INFO)
    jobs.roots()
    signal.signal(signal.SIGTERM,lambda *args:STOP.set())
    signal.signal(signal.SIGINT,lambda *args:STOP.set())
    while not STOP.is_set():
        try:
            job=jobs.claim_next()
            if job:
                if job['_kind']=='display':
                    import display_jobs
                    display_jobs.execute(job)
                elif job['_kind']=='media':
                    import media_worker
                    media_worker.execute(job)
                else: execute(job)
            else:
                from services.panorama_coverage import refresh
                if not refresh():STOP.wait(2)
        except Exception:
            log.exception('Worker database unavailable');STOP.wait(5)


if __name__=='__main__': main()
