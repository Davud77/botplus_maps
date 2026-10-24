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
    from controllers.data_import import upload_original
    return upload_original(field_name=field_name)


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


@imports_blueprint.get('/tasks')
def all_tasks():
    editor()
    result=[]
    with Database().cursor() as cur:
        for kind,table in jobs.TABLES.items():
            cur.execute(f'''SELECT j.* FROM {table} j WHERE (%s OR j.owner_id=%s)
                AND NOT EXISTS(SELECT 1 FROM task_dismissals d WHERE d.owner_id=%s AND d.kind=%s
                    AND d.job_id=j.id AND d.dismissed_at>=j.updated_at AND j.status NOT IN ('queued','running'))''',
                (g.current_user['role']=='admin',g.current_user_id,g.current_user_id,kind))
            for row in cur.fetchall():
                if kind=='media':
                    item={'id':str(row['id']),'title':'Импорт панорам: '+row['source'].get('title',row['source']['key']),
                          'status':row['status'],'progress':100 if row['status']=='succeeded' else (min(99,round(row['processed']*100/row['total'])) if row.get('total') else None),
                          'message':row['message'],'created_at':row['created_at'],
                          'counts':{k:row[k] for k in ('processed','imported','skipped','failed')}}
                elif kind=='display':
                    from display_jobs import serialize
                    item=serialize(row)
                else:
                    item=jobs.serialize(row)
                    if row['source'].get('operation')=='register-folder' and row.get('result'):
                        item['counts']={**row['result'],'skipped':0}
                item['kind']=kind;result.append(item)
    rank={'running':0,'queued':1}
    result.sort(key=lambda j:(rank.get(j['status'],2),j['created_at'],j['id']))
    return jsonify(jobs=result)


@imports_blueprint.post('/tasks/<kind>/<uuid:job_id>/done')
def dismiss_task(kind,job_id):
    editor()
    table=jobs.TABLES.get(kind)
    if not table:abort(404)
    with Database().cursor(write=True) as cur:
        cur.execute(f'SELECT owner_id,status FROM {table} WHERE id=%s FOR UPDATE',(str(job_id),))
        row=cur.fetchone()
        if not row or (row['owner_id']!=g.current_user_id and g.current_user['role']!='admin'):abort(404)
        if row['status'] in {'queued','running'}:abort(409)
        cur.execute('''INSERT INTO task_dismissals(owner_id,kind,job_id) VALUES (%s,%s,%s)
            ON CONFLICT(owner_id,kind,job_id) DO UPDATE SET dismissed_at=NOW()''',(g.current_user_id,kind,str(job_id)))
    return jsonify(ok=True)
