"""Explicit, durable preparation of map derivatives; originals remain authoritative."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import uuid
from psycopg2.extras import Json
from database import Database
import import_jobs as imports


def initialize(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS raster_display_jobs (
        id UUID PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
        idempotency_key TEXT NOT NULL, source JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
        attempts INTEGER NOT NULL DEFAULT 0, progress INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT 'В очереди', error TEXT, cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
        lease_token UUID, lease_until TIMESTAMPTZ, result JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(owner_id,idempotency_key)
    )''')
    cur.execute('CREATE INDEX IF NOT EXISTS raster_display_claim_idx ON raster_display_jobs(status,lease_until,created_at)')
    cur.execute('''CREATE TABLE IF NOT EXISTS raster_display_events (
        id BIGSERIAL PRIMARY KEY, job_id UUID NOT NULL REFERENCES raster_display_jobs(id),
        at TIMESTAMPTZ NOT NULL DEFAULT NOW(), message TEXT NOT NULL
    )''')
    cur.execute('CREATE INDEX IF NOT EXISTS raster_display_events_job_idx ON raster_display_events(job_id,id DESC)')


def event(cur,job_id,message):
    cur.execute('INSERT INTO raster_display_events(job_id,message) VALUES (%s,%s)',(str(job_id),message))
    cur.execute("INSERT INTO system_events(service,message) VALUES ('display-worker',%s)",(message,))


def base_asset(asset):
    value=deepcopy(asset);value.pop('display',None);return value


def signature(asset,max_zoom):
    return hashlib.sha256(json.dumps({'asset':base_asset(asset),'max_zoom':max_zoom,'recipe':'map-cog-v1'},sort_keys=True).encode()).hexdigest()


def display_path(asset,z,scale):
    """Optional derivative. Missing products fall back to validated native data."""
    display=asset.get('display')
    if not isinstance(display,dict):return None
    try:
        zoom=display['max_map_zoom']
        if type(zoom) is not int or not 12<=zoom<=23 or z+int(math.log2(scale))>zoom:return None
        if display['signature']!=signature(asset,zoom):return None
        root=imports.products_root().resolve(strict=True);path=(root/display['key']).resolve(strict=True)
        if not path.is_relative_to(root) or imports.fingerprint(path)!=display['fingerprint']:return None
        return path
    except (OSError,ValueError,KeyError,TypeError):return None


def enqueue(owner_id,ortho_id,max_zoom=21,db=None):
    if type(max_zoom) is not int or not 12<=max_zoom<=23:raise ValueError('Масштаб подготовки: от 12 до 23.')
    db=db or Database();asset=imports.asset_record(ortho_id,db)
    if not asset:raise ValueError('Сначала подключите оригинал через импорт с диска/NAS.')
    imports.asset_path(asset)
    with db.cursor() as cur:
        cur.execute('SELECT filename FROM orthophotos WHERE id=%s',(ortho_id,));row=cur.fetchone()
        if not row:raise ValueError('Слой больше не существует.')
        title=row['filename']
    sig=signature(asset,max_zoom)
    source={'asset':base_asset(asset),'ortho_id':ortho_id,'title':'Для карты: '+title,'max_zoom':max_zoom,'signature':sig}
    with db.cursor(write=True) as cur:
        cur.execute('''INSERT INTO raster_display_jobs(id,owner_id,idempotency_key,source) VALUES (%s,%s,%s,%s)
            ON CONFLICT(owner_id,idempotency_key) DO NOTHING RETURNING *''',(str(uuid.uuid4()),owner_id,f'{ortho_id}:{sig}',Json(source)))
        job=cur.fetchone()
        if job:event(cur,job['id'],'Подготовка для быстрого показа поставлена в очередь. Оригинал сохраняется.')
        else:
            cur.execute('SELECT * FROM raster_display_jobs WHERE owner_id=%s AND idempotency_key=%s FOR UPDATE',(owner_id,f'{ortho_id}:{sig}'));job=cur.fetchone()
            if job['status']=='succeeded' and (not display_path(asset,0,1) or asset.get('display',{}).get('signature')!=sig):
                cur.execute("UPDATE raster_display_jobs SET status='queued',attempts=0,progress=0,result=NULL,error=NULL,cancel_requested=FALSE,updated_at=NOW() WHERE id=%s RETURNING *",(str(job['id']),));job=cur.fetchone()
                event(cur,job['id'],'Производная недоступна; создан повторный запуск.')
    return dict(job)


def serialize(job):
    result={key:job[key] for key in ['status','attempts','progress','message','error','cancel_requested','created_at','updated_at']}
    result.update(id=str(job['id']),title=job['source']['title'],ortho_id=job['source']['ortho_id'])
    return result


def prepare_file(source,folder,max_zoom,progress):
    from osgeo import gdal
    gdal.UseExceptions();gdal.SetCacheMax(128*1024**2)
    original=gdal.Open(str(source))
    if not original or not original.GetProjectionRef():raise ValueError('У исходника нет известной проекции. Сначала задайте правильную привязку при подготовке.')
    if not 1<=original.RasterCount<=4:raise ValueError('Для отображения выберите от одного до четырёх каналов.')
    if original.RasterCount==1 and original.GetRasterBand(1).GetRasterColorTable():
        original=gdal.Translate('',original,format='VRT',rgbExpand='rgba')
    vrt=gdal.AutoCreateWarpedVRT(original,None,'EPSG:3857')
    transform=vrt.GetGeoTransform();native=max(abs(transform[1]),abs(transform[5]))
    resolution=max(native,40075016.68557849/(256*2**max_zoom));span=resolution*512;half=20037508.342789244
    west=max(-half,transform[0]);east=min(half,transform[0]+transform[1]*vrt.RasterXSize)
    south=max(-half,transform[3]+transform[5]*vrt.RasterYSize);north=min(half,transform[3]);vrt=None
    if not all(math.isfinite(n) for n in [west,east,south,north,resolution]) or west>=east or south>=north:raise ValueError('Источник находится вне области отображения карты.')
    bounds=[math.floor(west/span)*span,math.floor(south/span)*span,math.ceil(east/span)*span,math.ceil(north/span)*span]
    width=round((bounds[2]-bounds[0])/resolution);height=round((bounds[3]-bounds[1])/resolution)
    raw=width*height*sum(max(1,gdal.GetDataTypeSize(original.GetRasterBand(i).DataType)//8) for i in range(1,original.RasterCount+1))
    if shutil.disk_usage(folder).free<raw*3+512*1024**2:raise ValueError('Недостаточно свободного места на NAS для производной и временных файлов.')
    output=folder/'display.tif'
    result=gdal.Warp(str(output),original,options=gdal.WarpOptions(format='COG',dstSRS='EPSG:3857',xRes=resolution,yRes=resolution,outputBounds=bounds,dstAlpha=True,resampleAlg='near',warpMemoryLimit=128,warpOptions=['NUM_THREADS=2'],creationOptions=['COMPRESS=DEFLATE','LEVEL=1','BLOCKSIZE=512','BIGTIFF=IF_SAFER','NUM_THREADS=2','OVERVIEWS=AUTO','OVERVIEW_RESAMPLING=NEAREST'],callback=progress))
    if result is None:raise RuntimeError('Подготовка не завершена.')
    result=None;original=None
    return output


def execute(job,db=None,reuse=None):
    from job_worker import Lease,LeaseLost,STOP
    from geo.raster import inspect_raster
    db=db or Database();lease=Lease(job,db,table='raster_display_jobs',event_writer=event);lease.thread.start()
    folder=None;keep=False
    try:
        source=job['source'];asset=source['asset'];original=imports.asset_path(asset)
        lease.progress(2,'Подготовка производной для быстрого переключения масштабов',record=True)
        current=imports.asset_record(source['ortho_id'],db)
        existing=display_path(current,0,1) if current else None
        if existing and current['display']['signature']==source['signature']:
            output=existing
        elif reuse is not None:
            # Operator-only adoption of a measured product, never an API parameter.
            output=Path(reuse).resolve(strict=True)
            if not output.is_relative_to(imports.products_root().resolve(strict=True)):raise ValueError('Производная должна находиться в управляемом хранилище.')
        else:
            folder=imports.products_root()/'display'/str(job['id'])/str(job['lease_token']);folder.mkdir(parents=True,exist_ok=False)
            last=[-1]
            def progress(fraction,message,data):
                if STOP.is_set() or lease.lost.is_set():return 0
                percent=5+int(fraction*85)
                if percent//5!=last[0]:
                    try:lease.progress(percent,'Подготовка производной на NAS');last[0]=percent//5
                    except Exception:return 0
                return 1
            output=prepare_file(original,folder,source['max_zoom'],progress)
        lease.progress(92,'Проверка производной и исходника',record=True)
        report=inspect_raster(output)
        if not report['cog_layout_hint'] or report.get('epsg') not in {3857,'3857'}:
            from osgeo import gdal,osr
            check=gdal.Open(str(output));srs=osr.SpatialReference(wkt=check.GetProjectionRef());check=None
            if not report['cog_layout_hint'] or srs.GetAuthorityCode(None)!='3857':raise ValueError('Производная должна быть COG в проекции карты.')
        imports.asset_path(asset);lease.check()
        display={'key':str(output.relative_to(imports.products_root())),'fingerprint':imports.fingerprint(output),'signature':source['signature'],'max_map_zoom':source['max_zoom']}
        with db.cursor(write=True) as cur:
            cur.execute("SELECT id FROM raster_display_jobs WHERE id=%s AND lease_token=%s AND status='running' AND lease_until>NOW() AND NOT cancel_requested FOR UPDATE",(str(job['id']),str(job['lease_token'])))
            if not cur.fetchone():raise LeaseLost('Задание отменено или потеряна аренда.')
            table='import_assets';cur.execute('SELECT asset FROM import_assets WHERE ortho_id=%s FOR UPDATE',(source['ortho_id'],));row=cur.fetchone()
            if not row:
                cur.execute("SELECT to_regclass('raster_sources') AS name")
                if cur.fetchone()['name']:
                    table='raster_sources';cur.execute('SELECT asset FROM raster_sources WHERE ortho_id=%s FOR UPDATE',(source['ortho_id'],));row=cur.fetchone()
            if not row or base_asset(row['asset'])!=asset:raise ValueError('Слой удалён или исходник переподключён. Создайте новое задание.')
            updated=dict(row['asset']);updated['display']=display
            cur.execute(f'UPDATE {table} SET asset=%s WHERE ortho_id=%s',(Json(updated),source['ortho_id']))
            cur.execute("UPDATE raster_display_jobs SET status='succeeded',progress=100,message='Готово для быстрого показа; оригинал сохранён',result=%s,lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s",(Json({'ortho_id':source['ortho_id'],'max_zoom':source['max_zoom']}),str(job['id'])))
            event(cur,job['id'],'Производная подключена к карте. Оригинал и исходная проекция сохранены.')
        keep=True;return display
    except Exception as exc:
        message=str(exc)
        for root in [imports.products_root(),imports.staging_root(),*imports.roots().values()]:message=message.replace(str(root),'[хранилище]')
        with db.cursor(write=True) as cur:
            cur.execute("""UPDATE raster_display_jobs SET status=CASE WHEN cancel_requested THEN 'cancelled' WHEN %s THEN 'queued' ELSE 'failed' END,
                attempts=CASE WHEN %s THEN greatest(0,attempts-1) ELSE attempts END,error=%s,message='Подготовка остановлена; оригинал сохранён',lease_token=NULL,lease_until=NULL,updated_at=NOW()
                WHERE id=%s AND lease_token=%s AND status='running' RETURNING id""",(STOP.is_set(),STOP.is_set(),message[:1000],str(job['id']),str(job['lease_token'])))
            if cur.fetchone():event(cur,job['id'],message[:1000])
        return None
    finally:
        lease.done.set();lease.thread.join(timeout=2)
        if folder and not keep:shutil.rmtree(folder,ignore_errors=True)
