"""Durable raster ingestion. Source files are never rewritten or removed."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import uuid
from psycopg2.extras import Json
try:
    from .database import Database
except ImportError:
    from database import Database

LEASE_SECONDS = 90
MAX_ATTEMPTS = 3


def initialize(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS import_jobs (
        id UUID PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
        idempotency_key VARCHAR(128) NOT NULL, source JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
        attempts INTEGER NOT NULL DEFAULT 0, progress INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT 'В очереди', error TEXT, cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
        lease_token UUID, lease_until TIMESTAMPTZ, result JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(owner_id,idempotency_key)
    )''')
    cursor.execute("CREATE INDEX IF NOT EXISTS import_jobs_claim_idx ON import_jobs(status,lease_until,created_at)")
    # The legacy orthophotos table is initialized separately; the controller
    # removes this registration atomically when unregistering an imported layer.
    cursor.execute('''CREATE TABLE IF NOT EXISTS import_assets (
        ortho_id INTEGER PRIMARY KEY, job_id UUID NOT NULL REFERENCES import_jobs(id),
        signature TEXT UNIQUE NOT NULL, asset JSONB NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS import_events (
        id BIGSERIAL PRIMARY KEY, job_id UUID NOT NULL REFERENCES import_jobs(id),
        at TIMESTAMPTZ NOT NULL DEFAULT NOW(), message TEXT NOT NULL
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS import_events_job_idx ON import_events(job_id,id DESC)')


def roots():
    value=json.loads(os.environ.get('LOCAL_SOURCE_ROOTS','{}'))
    if not isinstance(value,dict) or any(not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}',key) or not isinstance(path,str) or not Path(path).is_absolute() for key,path in value.items()):
        raise ValueError('LOCAL_SOURCE_ROOTS must be a JSON object of root IDs and absolute folders')
    return {key:Path(path) for key,path in value.items()}


def staging_root():
    return Path(os.environ.get('IMPORT_STAGING_DIR','/app/data/import-staging'))


def products_root():
    return Path(os.environ.get('IMPORT_PRODUCTS_DIR','/app/data/import-products'))


def resolve_source(root_id,key,*,internal=False):
    if not isinstance(key,str) or not key or '\\' in key or '\x00' in key:
        raise ValueError('Укажите относительный путь к GeoTIFF.')
    relative=PurePosixPath(key)
    if relative.is_absolute() or '..' in relative.parts or relative.suffix.lower() not in {'.tif','.tiff'}:
        raise ValueError('Разрешены только относительные пути к .tif/.tiff внутри источника.')
    root=staging_root() if internal and root_id=='__uploads' else roots().get(root_id)
    if root is None: raise ValueError('Источник не подключён администратором.')
    root=root.resolve(strict=True)
    path=(root/str(relative)).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file(): raise ValueError('Файл находится вне разрешённого источника.')
    return path


def fingerprint(path):
    stat=path.stat()
    return {key:getattr(stat,key) for key in ['st_size','st_mtime_ns','st_ctime_ns','st_dev','st_ino']}


def event(cursor,job_id,message):
    cursor.execute('INSERT INTO import_events (job_id,message) VALUES (%s,%s)',(str(job_id),message))


def enqueue(owner_id,root_id,key,*,title='',crs_id=None,idempotency_key=None,internal=False,db=None):
    db=db or Database()
    if not isinstance(root_id,str) or (root_id=='__uploads' and not internal): raise ValueError('Неверный источник.')
    if not isinstance(title,str) or len(title)>120: raise ValueError('Название: до 120 символов.')
    path=resolve_source(root_id,key,internal=internal)
    definition=None
    if crs_id is not None:
        if not isinstance(crs_id,str): raise ValueError('Неверная СК.')
        with db.cursor() as cursor:
            cursor.execute('SELECT definition FROM coordinate_systems WHERE id=%s',(crs_id,))
            row=cursor.fetchone()
        if not row: raise ValueError('Система координат не найдена.')
        definition=row['definition']
    source={'root_id':root_id,'key':key,'fingerprint':fingerprint(path),'source_crs':definition,'title':title.strip() or path.name,'recipe':1}
    signature=hashlib.sha256(json.dumps({k:v for k,v in source.items() if k!='title'},sort_keys=True).encode()).hexdigest()
    source['signature']=signature
    token=idempotency_key or signature
    if not isinstance(token,str) or not 1<=len(token)<=128: raise ValueError('Ключ идемпотентности: 1–128 символов.')
    with db.cursor(write=True) as cursor:
        job_id=str(uuid.uuid4())
        cursor.execute('''INSERT INTO import_jobs (id,owner_id,idempotency_key,source) VALUES (%s,%s,%s,%s)
            ON CONFLICT(owner_id,idempotency_key) DO NOTHING RETURNING *''',(job_id,owner_id,token,Json(source)))
        row=cursor.fetchone()
        if row: event(cursor,job_id,'Задание поставлено в очередь.')
        else:
            cursor.execute('SELECT * FROM import_jobs WHERE owner_id=%s AND idempotency_key=%s',(owner_id,token))
            row=cursor.fetchone()
            if row['source']['signature']!=signature: raise ValueError('Ключ уже использован для другого источника или версии файла.')
            if row['status']=='succeeded':
                cursor.execute('SELECT 1 FROM import_assets WHERE ortho_id=%s',(row['result']['ortho_id'],))
                if not cursor.fetchone():
                    cursor.execute("UPDATE import_jobs SET status='queued',result=NULL,progress=0,attempts=0,message='Повторная регистрация',updated_at=NOW() WHERE id=%s RETURNING *",(str(row['id']),))
                    row=cursor.fetchone()
                    event(cursor,row['id'],'Повторная регистрация удалённого слоя.')
    return dict(row)


def serialize(row):
    value={key:row[key] for key in ['id','status','attempts','progress','message','error','cancel_requested','result','created_at','updated_at']}
    value['id']=str(value['id'])
    value['title']=row['source']['title']
    value['root_id']=row['source']['root_id']
    value['key']=row['source']['key']
    return value


def claim(db=None):
    db=db or Database()
    with db.cursor(write=True) as cursor:
        cursor.execute("""UPDATE import_jobs SET status=CASE WHEN cancel_requested THEN 'cancelled' ELSE 'failed' END,
            message='Предыдущий worker не завершил задание. Доступен повторный запуск.',lease_token=NULL,lease_until=NULL,updated_at=NOW()
            WHERE status='running' AND lease_until<NOW() AND (attempts>=%s OR cancel_requested)""",(MAX_ATTEMPTS,))
        cursor.execute("""WITH candidate AS (SELECT id FROM import_jobs
            WHERE (status='queued' OR (status='running' AND lease_until<NOW())) AND NOT cancel_requested AND attempts<%s
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
            UPDATE import_jobs j SET status='running',attempts=attempts+1,progress=0,error=NULL,
                message='Проверка источника',lease_token=%s,lease_until=NOW()+make_interval(secs=>%s),updated_at=NOW()
            FROM candidate c WHERE j.id=c.id RETURNING j.*""",(MAX_ATTEMPTS,str(uuid.uuid4()),LEASE_SECONDS))
        row=cursor.fetchone()
        if row: event(cursor,row['id'],f"Начата попытка {row['attempts']}.")
    return dict(row) if row else None


def asset_record(ortho_id,db=None):
    with (db or Database()).cursor() as cursor:
        cursor.execute('SELECT asset FROM import_assets WHERE ortho_id=%s',(ortho_id,))
        row=cursor.fetchone()
    return row['asset'] if row else None


def asset_path(asset):
    # Verify the original even for derived files: changing it requires an explicit
    # new import rather than silently serving a different source version.
    source=asset['source']
    path=resolve_source(source['root_id'],source['key'],internal=True)
    if fingerprint(path)!=source['fingerprint']: raise ValueError('Исходный файл изменён. Требуется новый импорт.')
    if asset['kind']=='source': return path
    root=products_root().resolve(strict=True)
    result=(root/asset['key']).resolve(strict=True)
    if not result.is_relative_to(root) or fingerprint(result)!=asset['fingerprint']: raise ValueError('Подготовленный файл отсутствует или изменён.')
    return result
