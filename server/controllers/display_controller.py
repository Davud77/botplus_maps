from flask import Blueprint,abort,g,jsonify,request
from database import Database
import display_jobs as jobs
from controllers.import_controller import editor

display_blueprint=Blueprint('raster_display',__name__)


def own(cur,job_id):
    cur.execute('SELECT * FROM raster_display_jobs WHERE id=%s FOR UPDATE',(str(job_id),));row=cur.fetchone()
    if not row or (row['owner_id']!=g.current_user_id and g.current_user['role']!='admin'):abort(404)
    return row


@display_blueprint.post('/raster-display/orthophotos/<int:ortho_id>')
def enqueue(ortho_id):
    editor();request.max_content_length=1000
    body=request.get_json(silent=True)
    if body is None:body={}
    if not isinstance(body,dict) or set(body)-{'max_zoom'}:abort(400)
    try:job=jobs.enqueue(g.current_user_id,ortho_id,body.get('max_zoom',21))
    except (ValueError,OSError) as error:abort(400,description=str(error) if isinstance(error,ValueError) else 'Исходник недоступен на подключённом диске.')
    return jsonify(job=jobs.serialize(job)),202


@display_blueprint.get('/raster-display/jobs')
def listing():
    editor()
    with Database().cursor() as cur:
        cur.execute('SELECT * FROM raster_display_jobs WHERE (%s OR owner_id=%s) ORDER BY created_at DESC,id LIMIT 50',(g.current_user['role']=='admin',g.current_user_id));rows=cur.fetchall()
    return jsonify(jobs=[jobs.serialize(row) for row in rows])


@display_blueprint.get('/raster-display/jobs/<uuid:job_id>')
def detail(job_id):
    editor()
    with Database().cursor(write=True) as cur:
        row=own(cur,job_id)
        cur.execute('SELECT at,message FROM raster_display_events WHERE job_id=%s ORDER BY id DESC LIMIT 100',(str(job_id),));events=list(reversed(cur.fetchall()))
    return jsonify(job=jobs.serialize(row),events=events)


@display_blueprint.post('/raster-display/jobs/<uuid:job_id>/<action>')
def action(job_id,action):
    editor()
    with Database().cursor(write=True) as cur:
        row=own(cur,job_id)
        if action=='cancel' and row['status'] in {'queued','running'}:
            cur.execute("UPDATE raster_display_jobs SET cancel_requested=TRUE,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,message='Запрошена отмена',updated_at=NOW() WHERE id=%s",(str(job_id),))
            jobs.event(cur,job_id,'Запрошена отмена подготовки; оригинал сохраняется.')
        elif action=='retry' and row['status'] in {'failed','cancelled'}:
            cur.execute("UPDATE raster_display_jobs SET status='queued',attempts=0,progress=0,cancel_requested=FALSE,error=NULL,message='Повторная подготовка',updated_at=NOW() WHERE id=%s",(str(job_id),))
            jobs.event(cur,job_id,'Задание возвращено в очередь.')
        else:abort(409,description='Действие недоступно для текущего состояния задания.')
    return jsonify(ok=True)
