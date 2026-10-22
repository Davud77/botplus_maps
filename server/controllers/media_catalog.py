"""Paged media catalog, logical folders and reversible bulk operations."""
import math
from flask import Blueprint, request, jsonify, abort
from psycopg2 import errors
from psycopg2.extras import Json
from uuid import uuid4
from flask import g
try:
    from ..database import Database
    from ..services.media_metadata import display_name
except ImportError:
    from database import Database
    from services.media_metadata import display_name

media_blueprint = Blueprint('media_catalog', __name__)
database = Database()


def initialize(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS panorama_folders (
        id BIGSERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    for definition in ['folder_id BIGINT REFERENCES panorama_folders(id) ON DELETE SET NULL',
                       'deleted_at TIMESTAMPTZ', "tags TEXT NOT NULL DEFAULT ''",
                       'media_type TEXT', 'width INTEGER', 'height INTEGER', 'source_ref JSONB']:
        cur.execute('ALTER TABLE public.photos_4326 ADD COLUMN IF NOT EXISTS ' + definition)
    cur.execute('CREATE INDEX IF NOT EXISTS photos_folder_active_idx ON public.photos_4326(folder_id,id DESC) WHERE deleted_at IS NULL')
    cur.execute("CREATE TABLE IF NOT EXISTS system_events (id BIGSERIAL PRIMARY KEY,at TIMESTAMPTZ NOT NULL DEFAULT NOW(),service TEXT NOT NULL,level TEXT NOT NULL DEFAULT 'info',message TEXT NOT NULL)")
    cur.execute('CREATE INDEX IF NOT EXISTS photos_trash_idx ON public.photos_4326(id DESC) WHERE deleted_at IS NOT NULL')
    cur.execute('''CREATE TABLE IF NOT EXISTS media_import_jobs (
        id UUID PRIMARY KEY, owner_id INTEGER NOT NULL, source JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued', processed BIGINT NOT NULL DEFAULT 0,
        imported BIGINT NOT NULL DEFAULT 0, skipped BIGINT NOT NULL DEFAULT 0,
        failed BIGINT NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT 'В очереди',
        cancel_requested BOOLEAN NOT NULL DEFAULT FALSE, lease_token UUID, lease_until TIMESTAMPTZ,
        attempts INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    cur.execute('CREATE INDEX IF NOT EXISTS media_import_claim_idx ON media_import_jobs(status,lease_until,created_at)')
    cur.execute('''CREATE TABLE IF NOT EXISTS media_import_sources (
        signature TEXT PRIMARY KEY, photo_id INTEGER NOT NULL REFERENCES public.photos_4326(id) ON DELETE CASCADE)''')


def filters():
    clauses = ['deleted_at IS NOT NULL' if request.args.get('trash') == '1' else 'deleted_at IS NULL']
    values = []
    folder = request.args.get('folder', 'all')
    if folder == 'unfiled': clauses.append('folder_id IS NULL')
    elif folder != 'all':
        try: folder = int(folder)
        except (ValueError, TypeError): abort(400)
        clauses.append('folder_id=%s'); values.append(folder)
    query = request.args.get('q', '').strip()
    if len(query) > 120: abort(400)
    if query:
        literal = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        clauses.append("(filename ILIKE %s OR tags ILIKE %s)"); values += ['%' + literal + '%'] * 2
    return ' AND '.join(clauses), values


@media_blueprint.get('/media/catalog')
def catalog():
    where, values = filters()
    try:
        limit = min(100, max(1, int(request.args.get('limit', 50))))
        after = int(request.args.get('after', 0))
    except ValueError: abort(400)
    if after: where += ' AND id<%s'; values.append(after)
    with database.cursor() as cur:
        cur.execute('''SELECT id,filename,folder_id,tags,media_type,width,height,
            ST_Y(geom) AS latitude,ST_X(geom) AS longitude,"timestamp",deleted_at
            FROM public.photos_4326 WHERE ''' + where + ' ORDER BY id DESC LIMIT %s', values + [limit + 1])
        rows = cur.fetchall()
    more = len(rows) > limit
    items = [{**dict(row), 'name': display_name(row['filename'])} for row in rows[:limit]]
    return jsonify(items=items, next_cursor=items[-1]['id'] if more else None)


@media_blueprint.get('/media/folders')
def folders():
    with database.cursor() as cur:
        cur.execute('SELECT id,name FROM panorama_folders ORDER BY lower(name),id')
        rows = cur.fetchall()
    return jsonify(folders=rows)


@media_blueprint.post('/media/folders')
def create_folder():
    body = request.get_json(silent=True) or {}
    if not isinstance(body,dict): abort(400)
    name = body.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120: abort(400, description='Название папки: от 1 до 120 символов.')
    try:
        with database.cursor(write=True) as cur:
            cur.execute('INSERT INTO panorama_folders(name) VALUES (%s) RETURNING id,name', (name.strip(),))
            row = cur.fetchone()
    except errors.UniqueViolation: abort(409, description='Папка с таким названием уже существует.')
    return jsonify(folder=row), 201


@media_blueprint.route('/media/folders/<int:folder_id>', methods=['PATCH', 'DELETE'])
def change_folder(folder_id):
    try:
        with database.cursor(write=True) as cur:
            cur.execute('SELECT id FROM panorama_folders WHERE id=%s FOR UPDATE', (folder_id,))
            if not cur.fetchone(): abort(404)
            if request.method == 'DELETE':
                cur.execute('SELECT 1 FROM public.photos_4326 WHERE folder_id=%s LIMIT 1', (folder_id,))
                if cur.fetchone(): abort(409, description='Сначала переместите файлы из папки, включая корзину.')
                cur.execute('DELETE FROM panorama_folders WHERE id=%s', (folder_id,))
            else:
                name = (request.get_json(silent=True) or {}).get('name')
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120: abort(400)
                cur.execute('UPDATE panorama_folders SET name=%s WHERE id=%s', (name.strip(), folder_id))
    except errors.UniqueViolation: abort(409, description='Папка с таким названием уже существует.')
    return jsonify(status='ok')


@media_blueprint.post('/media/bulk')
def bulk():
    request.max_content_length = 20000
    body = request.get_json(silent=True) or {}
    if not isinstance(body,dict): abort(400)
    ids, action = body.get('ids'), body.get('action')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or any(type(i) is not int or i <= 0 for i in ids): abort(400)
    ids = list(set(ids))
    with database.cursor(write=True) as cur:
        cur.execute('SELECT id FROM public.photos_4326 WHERE id=ANY(%s) FOR UPDATE', (ids,))
        if len(cur.fetchall()) != len(ids): abort(404, description='Часть выбранных файлов уже недоступна. Обновите список.')
        if action == 'move':
            folder = body.get('folder_id')
            if folder is not None:
                if type(folder) is not int: abort(400)
                cur.execute('SELECT id FROM panorama_folders WHERE id=%s FOR KEY SHARE', (folder,))
                if not cur.fetchone(): abort(404, description='Папка не найдена.')
            cur.execute('UPDATE public.photos_4326 SET folder_id=%s WHERE id=ANY(%s)', (folder, ids))
        elif action == 'trash':
            cur.execute('UPDATE public.photos_4326 SET deleted_at=COALESCE(deleted_at,NOW()) WHERE id=ANY(%s)', (ids,))
        elif action == 'restore':
            cur.execute('UPDATE public.photos_4326 SET deleted_at=NULL WHERE id=ANY(%s)', (ids,))
        elif action == 'tags':
            tags = body.get('tags')
            if not isinstance(tags, str) or len(tags) > 2000: abort(400)
            cur.execute('UPDATE public.photos_4326 SET tags=%s WHERE id=ANY(%s)', (tags, ids))
        else: abort(400)
        cur.execute("INSERT INTO system_events(service,message) VALUES ('catalog',%s)",(f'{action}: {len(ids)} selected records',))
    return jsonify(status='ok', affected=len(ids))


@media_blueprint.get('/media/bounds')
def bounds():
    where, values = filters()
    with database.cursor() as cur:
        cur.execute('SET LOCAL statement_timeout=3000')
        cur.execute('SELECT ST_XMin(b) AS west,ST_YMin(b) AS south,ST_XMax(b) AS east,ST_YMax(b) AS north FROM (SELECT ST_Extent(geom) AS b FROM public.photos_4326 WHERE ' + where + ') extent', values)
        row = cur.fetchone()
    return jsonify(bounds=dict(row) if row and row['west'] is not None else None)


@media_blueprint.get('/media/markers')
def markers():
    where, values = filters()
    try:
        west, south, east, north = [float(request.args[k]) for k in ('west','south','east','north')]
        zoom = min(24, max(0, int(request.args.get('zoom', 5))))
        if not all(math.isfinite(v) for v in (west,south,east,north)): raise ValueError()
    except (ValueError, KeyError): abort(400)
    where += ' AND geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)'
    values += [max(-180,west),max(-90,south),min(180,east),min(90,north)]
    grid = max(.0005, 20 / 2 ** zoom) if zoom <= 17 else None
    if grid:
        query = 'SELECT min(id) AS id,avg(ST_Y(geom)) AS lat,avg(ST_X(geom)) AS lng,count(*) AS count FROM public.photos_4326 WHERE ' + where + ' GROUP BY ST_SnapToGrid(geom,%s) LIMIT 5000'
        values.append(grid)
    else:
        query = 'SELECT id,ST_Y(geom) AS lat,ST_X(geom) AS lng,1 AS count FROM public.photos_4326 WHERE ' + where + ' ORDER BY id DESC LIMIT 5000'
    with database.cursor() as cur:
        cur.execute(query, values); rows = cur.fetchall()
    return jsonify(rows)


@media_blueprint.route('/media/imports', methods=['GET','POST'])
def media_imports():
    if g.current_user['role']=='viewer': abort(403)
    if request.method=='POST':
        from media_worker import source_path
        body=request.get_json(silent=True) or {}
        if not isinstance(body,dict):abort(400)
        root,key=body.get('root_id'),body.get('key','')
        if type(body.get('only_360',True)) is not bool:abort(400)
        try:source_path(root,key)
        except (ValueError,OSError) as e:abort(400,description=str(e) if isinstance(e,ValueError) else 'Источник недоступен.')
        source={'root_id':root,'key':key,'only_360':body.get('only_360',True)}
        with database.cursor(write=True) as c:
            c.execute('INSERT INTO media_import_jobs(id,owner_id,source) VALUES (%s,%s,%s) RETURNING id',(str(uuid4()),g.current_user_id,Json(source)))
            row=c.fetchone()
        return jsonify(job=row),202
    with database.cursor() as c:
        c.execute("SELECT id,source,status,processed,imported,skipped,failed,message,created_at FROM media_import_jobs WHERE (%s OR owner_id=%s) ORDER BY created_at DESC LIMIT 50",(g.current_user['role']=='admin',g.current_user_id));rows=c.fetchall()
    return jsonify(jobs=rows)


@media_blueprint.post('/media/imports/<uuid:job_id>/<action>')
def media_action(job_id,action):
    if g.current_user['role']=='viewer':abort(403)
    with database.cursor(write=True) as c:
        c.execute('SELECT * FROM media_import_jobs WHERE id=%s FOR UPDATE',(str(job_id),));row=c.fetchone()
        if not row or (row['owner_id']!=g.current_user_id and g.current_user['role']!='admin'):abort(404)
        if action=='cancel' and row['status'] in {'queued','running'}:
            c.execute("UPDATE media_import_jobs SET cancel_requested=TRUE,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=%s",(str(job_id),))
        elif action=='retry' and row['status'] in {'failed','cancelled','succeeded'}:
            c.execute("UPDATE media_import_jobs SET status='queued',cancel_requested=FALSE,lease_until=NULL,lease_token=NULL WHERE id=%s",(str(job_id),))
        else:abort(409)
    return jsonify(status='ok')
