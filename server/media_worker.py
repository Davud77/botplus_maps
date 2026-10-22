"""Durable, bounded-memory media imports from read-only NAS sources."""
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import signal
import threading
from uuid import uuid4
from psycopg2.extras import Json
from database import Database
import config
import import_jobs
from storage import FileStorage
from services.media_metadata import read_media_metadata
from controllers.pano_controller import PanoController
from werkzeug.utils import secure_filename

STOP = threading.Event()
log = logging.getLogger(__name__)


def source_path(root_id, key):
    if not isinstance(root_id,str) or not isinstance(key,str) or '\\' in key or '\x00' in key: raise ValueError('Укажите путь внутри источника.')
    relative=PurePosixPath(key or '.')
    if relative.is_absolute() or '..' in relative.parts: raise ValueError('Разрешён только относительный путь.')
    root=import_jobs.roots().get(root_id)
    if root is None: raise ValueError('Источник не подключён.')
    root=root.resolve(strict=True);path=(root/str(relative)).resolve(strict=True)
    if not path.is_relative_to(root): raise ValueError('Файл находится вне подключённого источника.')
    if not path.is_dir() and path.suffix.lower() not in {'.jpg','.jpeg','.webp'}: raise ValueError('Выберите папку или JPEG/WebP.')
    return root,path


def signature(root_id,key,fingerprint):
    return hashlib.sha256(json.dumps([root_id,key,fingerprint],sort_keys=True).encode()).hexdigest()


def files(path):
    if path.is_file(): yield path;return
    for parent,dirs,names in os.walk(path,followlinks=False):
        dirs[:]=[n for n in dirs if not n.startswith(('@','#','.')) and not (Path(parent)/n).is_symlink()]
        for name in names:
            candidate=Path(parent)/name
            if candidate.suffix.lower() in {'.jpg','.jpeg','.webp'}: yield candidate


def claim(db):
    token=str(uuid4())
    with db.cursor(write=True) as c:
        c.execute("UPDATE media_import_jobs SET status='cancelled',lease_token=NULL,lease_until=NULL WHERE cancel_requested AND (status='queued' OR (status='running' AND lease_until<NOW()))")
        c.execute("""WITH job AS (SELECT id FROM media_import_jobs WHERE NOT cancel_requested AND
            (status='queued' OR (status='running' AND lease_until<NOW()))
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
            UPDATE media_import_jobs j SET status='running',lease_token=%s,
            lease_until=NOW()+INTERVAL '90 seconds',attempts=attempts+1,updated_at=NOW()
            FROM job WHERE j.id=job.id RETURNING j.*""",(token,))
        return c.fetchone()


def execute(job,db=None):
    db=db or Database();done=threading.Event();lost=threading.Event();jid=str(job['id']);token=str(job['lease_token'])
    def heartbeat():
        while not done.wait(5):
            try:
                with db.cursor(write=True) as c:
                    c.execute("UPDATE media_import_jobs SET lease_until=NOW()+INTERVAL '90 seconds',updated_at=NOW() WHERE id=%s AND lease_token=%s AND lease_until>NOW() AND NOT cancel_requested RETURNING id",(jid,token))
                    if not c.fetchone():lost.set();return
            except Exception:lost.set();return
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    counts={'processed':0,'imported':0,'skipped':0,'failed':0}
    parser=object.__new__(PanoController);last_error=''
    try:
        source=job['source'];root,path=source_path(source['root_id'],source['key'])
        for original in files(path):
            if STOP.is_set() or lost.is_set():raise InterruptedError('Обработка прервана; повтор продолжит импорт без дубликатов.')
            counts['processed']+=1;new_key=None;published=False
            try:
                actual=original.resolve(strict=True)
                if not actual.is_relative_to(root):raise ValueError('Ссылка ведёт за пределы источника.')
                key=str(original.relative_to(root));before=import_jobs.fingerprint(original);sig=signature(source['root_id'],key,before)
                with db.cursor() as c:
                    c.execute('SELECT photo_id FROM media_import_sources WHERE signature=%s',(sig,));known=c.fetchone()
                if known:counts['skipped']+=1;continue
                metadata=read_media_metadata(original)
                if source.get('only_360',True) and metadata['media_type']!='panorama':counts['skipped']+=1;continue
                with original.open('rb') as stream:lat,lon,alt,direction,dt=parser._parse_exif_data(stream)
                if lat is None or lon is None:raise ValueError('Нет GPS-координат в EXIF.')
                uid=uuid4().hex;safe=secure_filename(original.name)[:160] or 'panorama.jpg';new_key=f'{uid[:2]}/{uid[2:4]}/{uid}_{safe}'
                if import_jobs.fingerprint(original)!=before:raise ValueError('Исходник изменился во время импорта.')
                with db.cursor(write=True) as c:
                    c.execute("SELECT id FROM media_import_jobs WHERE id=%s AND lease_token=%s AND lease_until>NOW() AND NOT cancel_requested FOR UPDATE",(jid,token))
                    if not c.fetchone() or STOP.is_set():raise InterruptedError('Обработка отменена или потеряна аренда задания.')
                    c.execute('SELECT pg_advisory_xact_lock(%s)',(941027004,))
                    c.execute('SELECT photo_id FROM media_import_sources WHERE signature=%s',(sig,));existing=c.fetchone()
                    if existing:counts['skipped']+=1
                    else:
                        c.execute('''INSERT INTO public.photos_4326 (filename,path,geom,latitude,longitude,altitude,direction,"timestamp",directory,media_type,width,height,source_ref)
                            VALUES (%s,%s,ST_SetSRID(ST_MakePoint(%s,%s,%s),4326),%s,%s,%s,%s,%s,'panoramas',%s,%s,%s,%s) RETURNING id''',
                            (new_key,'panoramas/'+new_key,float(lon),float(lat),float(alt or 0),str(lat),str(lon),alt,direction,dt,metadata['media_type'],metadata['width'],metadata['height'],Json({'root_id':source['root_id'],'key':key,'fingerprint':before})))
                        identifier=c.fetchone()['id'];c.execute('INSERT INTO media_import_sources VALUES (%s,%s)',(sig,identifier));published=True;counts['imported']+=1
            except InterruptedError:raise
            except Exception as e:
                counts['failed']+=1;last_error=f'{original.name}: {type(e).__name__}'
                log.warning('Media import %s failed for one source: %s',jid,type(e).__name__)
            finally:
                with db.cursor(write=True) as c:
                    c.execute('''UPDATE media_import_jobs SET processed=%s,imported=%s,skipped=%s,failed=%s,message=%s,updated_at=NOW()
                        WHERE id=%s AND lease_token=%s''',(counts['processed'],counts['imported'],counts['skipped'],counts['failed'],last_error or 'Импорт файлов с NAS',jid,token))
        with db.cursor(write=True) as c:
            c.execute("UPDATE media_import_jobs SET status='succeeded',message=%s,lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s AND lease_token=%s AND lease_until>NOW() AND NOT cancel_requested",('Завершено с ошибками' if counts['failed'] else 'Импорт завершён',jid,token))
    except Exception as e:
        with db.cursor(write=True) as c:
            c.execute("UPDATE media_import_jobs SET status=CASE WHEN cancel_requested THEN 'cancelled' WHEN %s THEN 'queued' ELSE 'failed' END,message=%s,lease_token=NULL,lease_until=NULL,updated_at=NOW() WHERE id=%s AND lease_token=%s",(STOP.is_set() or lost.is_set(),str(e)[:250] if isinstance(e,InterruptedError) else 'Источник недоступен. Проверьте подключение NAS.',jid,token))
    finally:done.set();thread.join(timeout=2)


def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    db=Database()
    while not STOP.is_set():
        try:
            job=claim(db)
            if job:execute(job,db)
            else:STOP.wait(2)
        except Exception:log.exception('Media queue unavailable');STOP.wait(5)


if __name__=='__main__':main()
