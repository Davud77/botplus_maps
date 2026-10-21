import os
from pathlib import Path
from uuid import UUID,uuid4
from flask import Blueprint,abort,g,jsonify,request
from database import Database
import import_jobs as jobs

imports_blueprint=Blueprint('imports',__name__)


def editor():
    if g.current_user['role'] not in {'admin','editor'}: abort(403,description='Импорт доступен редактору и администратору.')


def own_job(job_id,cursor):
    cursor.execute('SELECT * FROM import_jobs WHERE id=%s FOR UPDATE',(str(job_id),))
    row=cursor.fetchone()
    if not row or (row['owner_id']!=g.current_user_id and g.current_user['role']!='admin'): abort(404)
    return row


@imports_blueprint.get('/imports/sources')
def sources():
    editor()
    return jsonify(sources=[{'id':key,'name':key} for key in jobs.roots()],upload_limit_bytes=int(os.environ.get('IMPORT_WEB_MAX_BYTES',str(2*1024**3))))


@imports_blueprint.post('/imports/jobs')
def enqueue():
    editor();request.max_content_length=24000
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or set(body)-{'root_id','key','title','source_crs_id','idempotency_key'}: abort(400)
    try:
        job=jobs.enqueue(g.current_user_id,body.get('root_id'),body.get('key'),title=body.get('title',''),crs_id=body.get('source_crs_id'),idempotency_key=body.get('idempotency_key'))
    except (ValueError,OSError) as exc: abort(400,description=str(exc) if isinstance(exc,ValueError) else 'Файл недоступен в подключённом источнике.')
    return jsonify(job=jobs.serialize(job)),202


@imports_blueprint.post('/imports/uploads')
def upload(field_name='file'):
    editor();request.max_content_length=int(os.environ.get('IMPORT_WEB_MAX_BYTES',str(2*1024**3)))
    file=request.files.get(field_name)
    if not file or Path(file.filename or '').suffix.lower() not in {'.tif','.tiff'}: abort(400,description='Выберите GeoTIFF .tif/.tiff.')
    root=jobs.staging_root();root.mkdir(parents=True,exist_ok=True)
    key=f'{uuid4()}.tif';path=root/key;queued=False
    try:
        with path.open('xb') as target:
            while True:
                chunk=file.stream.read(8*1024*1024)
                if not chunk: break
                target.write(chunk)
            target.flush();os.fsync(target.fileno())
        job=jobs.enqueue(g.current_user_id,'__uploads',key,title=request.form.get('title') or Path(file.filename).name,crs_id=request.form.get('source_crs_id') or None,internal=True)
        queued=True
        return jsonify(job=jobs.serialize(job),task_id=str(job['id']),status='started'),202
    except ValueError as exc: abort(400,description=str(exc))
    finally:
        if not queued: path.unlink(missing_ok=True)


@imports_blueprint.get('/imports/jobs')
def list_jobs():
    editor()
    try: offset=max(0,int(request.args.get('offset',0)))
    except ValueError: abort(400)
    with Database().cursor() as cur:
        cur.execute('''SELECT * FROM import_jobs WHERE (%s OR owner_id=%s)
            ORDER BY created_at DESC,id LIMIT 50 OFFSET %s''',(g.current_user['role']=='admin',g.current_user_id,offset))
        rows=cur.fetchall()
    return jsonify(jobs=[jobs.serialize(row) for row in rows])


@imports_blueprint.get('/imports/jobs/<uuid:job_id>')
def get_job(job_id):
    editor()
    with Database().cursor(write=True) as cur:
        row=own_job(job_id,cur)
        cur.execute('SELECT at,message FROM import_events WHERE job_id=%s ORDER BY id DESC LIMIT 100',(str(job_id),))
        events=list(reversed(cur.fetchall()))
    return jsonify(job=jobs.serialize(row),events=events)


@imports_blueprint.post('/imports/jobs/<uuid:job_id>/<action>')
def action(job_id,action):
    editor()
    with Database().cursor(write=True) as cur:
        row=own_job(job_id,cur)
        if action=='cancel':
            if row['status'] not in {'queued','running'}: abort(409,description='Задание уже завершено.')
            cur.execute("UPDATE import_jobs SET cancel_requested=TRUE,message=CASE WHEN status='queued' THEN 'Задание отменено' ELSE 'Отмена запрошена' END,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated_at=NOW() WHERE id=%s",(str(job_id),))
            jobs.event(cur,job_id,'Запрошена отмена. Исходник сохраняется.')
        elif action=='retry':
            if row['status'] not in {'failed','cancelled'}: abort(409,description='Повтор доступен для завершившихся с ошибкой или отменённых заданий.')
            cur.execute("UPDATE import_jobs SET status='queued',attempts=0,progress=0,error=NULL,cancel_requested=FALSE,lease_token=NULL,lease_until=NULL,message='Повторно в очереди',updated_at=NOW() WHERE id=%s",(str(job_id),))
            jobs.event(cur,job_id,'Задание повторно поставлено в очередь.')
        else: abort(404)
    return jsonify(status='ok')
