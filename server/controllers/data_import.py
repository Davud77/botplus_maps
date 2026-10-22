"""Register originals without pixel processing; browse only administrator roots."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from flask import Blueprint, abort, g, jsonify, request
from psycopg2.extras import Json
from database import Database
import import_jobs as jobs
from geo.raster import inspect_raster

data_import_blueprint=Blueprint('data_import',__name__)


def initialize(c):
    c.execute('ALTER TABLE coordinate_systems ADD COLUMN IF NOT EXISTS resolved BOOLEAN NOT NULL DEFAULT TRUE')
    c.execute('CREATE SEQUENCE IF NOT EXISTS unknown_projection_sequence')
    c.execute('''CREATE TABLE IF NOT EXISTS raster_sources (
        ortho_id INTEGER PRIMARY KEY,signature TEXT UNIQUE NOT NULL,asset JSONB NOT NULL,
        projection_id TEXT NOT NULL,warning TEXT NOT NULL DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_events (
        id BIGSERIAL PRIMARY KEY,at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        service TEXT NOT NULL,level TEXT NOT NULL DEFAULT 'info',message TEXT NOT NULL)''')


def event(c,message):
    c.execute("INSERT INTO system_events(service,message) VALUES ('import',%s)",(message,))


def editor():
    if g.current_user['role'] not in {'admin','editor'}:abort(403)


@data_import_blueprint.get('/imports/browse')
def browse():
    editor()
    from media_worker import source_path
    root_id=request.args.get('root_id');key=request.args.get('key','.')
    try:root,path=source_path(root_id,key)
    except (ValueError,OSError):abort(400,description='Папка недоступна в подключённом источнике.')
    if not path.is_dir():abort(400)
    try:after=max(0,int(request.args.get('offset',0)))
    except ValueError:abort(400)
    # scandir doesn't read file contents or construct a million-name browser list.
    kind=request.args.get('kind','all')
    extensions={'.tif','.tiff'} if kind=='raster' else {'.jpg','.jpeg','.webp'} if kind=='panoramas' else {'.tif','.tiff','.jpg','.jpeg','.webp'}
    entries=[];index=0;more=False
    with os.scandir(path) as iterator:
        for item in iterator:
            if item.name.startswith(('@','#','.')) or item.is_symlink():continue
            directory=item.is_dir(follow_symlinks=False)
            if not directory and Path(item.name).suffix.lower() not in extensions:continue
            if index<after:index+=1;continue
            if len(entries)>=100:more=True;break
            entries.append({'name':item.name,'key':str((path/item.name).relative_to(root)),'directory':directory})
    entries.sort(key=lambda e:(not e['directory'],e['name'].casefold()))
    current=str(path.relative_to(root))
    return jsonify(entries=entries,key=current,parent=str(path.parent.relative_to(root)) if path!=root else None,next_offset=after+len(entries) if more else None)


def register(root_id,key,title='',db=None):
    from osgeo import gdal,osr
    gdal.UseExceptions();osr.SetPROJEnableNetwork(False)
    db=db or Database();path=jobs.resolve_source(root_id,key,internal=True);before=jobs.fingerprint(path)
    source={'root_id':root_id,'key':key,'fingerprint':before,'source_crs':None,'recipe':1}
    sig=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    dataset=gdal.OpenEx(str(path),gdal.OF_RASTER|gdal.OF_READONLY,allowed_drivers=['GTiff'])
    if dataset is None:raise ValueError('Не удалось прочитать GeoTIFF.')
    definition=dataset.GetProjectionRef() or '';is_cog=dataset.GetMetadata('IMAGE_STRUCTURE').get('LAYOUT')=='COG';width=dataset.RasterXSize;height=dataset.RasterYSize;dataset=None
    report=None;warning=''
    try:report=inspect_raster(path)
    except (ValueError,RuntimeError):warning='Нет определённой проекции или привязки. Файл сохранён; положение на карте пока неизвестно.'
    if report and not is_cog:warning='Исходник подключён без обработки. Для быстрого просмотра можно отдельно подготовить COG в «Заданиях».'
    if jobs.fingerprint(path)!=before:raise ValueError('Файл изменился во время импорта.')
    with db.cursor(write=True) as c:
        c.execute('SELECT pg_advisory_xact_lock(%s)',(941027005,))
        c.execute('SELECT ortho_id FROM import_assets WHERE signature=%s UNION ALL SELECT ortho_id FROM raster_sources WHERE signature=%s LIMIT 1',(sig,sig));existing=c.fetchone()
        if existing:return {'ortho_id':existing['ortho_id'],'existing':True}
        c.execute('SELECT id,name,definition,resolved FROM coordinate_systems');catalog=c.fetchall();projection=None
        if definition:
            source_srs=osr.SpatialReference();source_srs.SetFromUserInput(definition)
            for entry in catalog:
                if not entry['definition'] or not entry['resolved']:continue
                candidate=osr.SpatialReference()
                try:
                    if candidate.SetFromUserInput(entry['definition'])==0 and source_srs.IsSame(candidate):projection=entry;break
                except RuntimeError:continue
        if projection is None:
            c.execute("SELECT nextval('unknown_projection_sequence') AS number");name='unknown_'+str(c.fetchone()['number'])
            c.execute('INSERT INTO coordinate_systems(id,name,definition,resolved) VALUES (%s,%s,%s,%s) RETURNING *',(name,name,definition,bool(definition and report)));projection=c.fetchone()
        c.execute('''INSERT INTO orthophotos(filename,bounds,crs,is_visible,is_cog,geometry) VALUES
            (%s,%s,%s,FALSE,%s,CASE WHEN %s IS NULL THEN NULL ELSE ST_Multi(ST_GeomFromText(%s,4326)) END) RETURNING id''',
            (title.strip()[:120] or path.name,json.dumps(report['native_bounds']) if report else None,projection['id'],is_cog,report['footprint_wkt'] if report else None,report['footprint_wkt'] if report else None))
        identifier=c.fetchone()['id'];asset={'source':source,'kind':'source'}
        c.execute('INSERT INTO raster_sources VALUES (%s,%s,%s,%s,%s)',(identifier,sig,Json(asset),projection['id'],warning))
        event(c,f'Импортирован ортофотоплан №{identifier} без обработки; проекция {projection["id"]}.')
    return {'ortho_id':identifier,'projection':projection['name'],'warning':warning,'width':width,'height':height,'existing':False}


@data_import_blueprint.post('/imports/register')
def register_source():
    editor();body=request.get_json(silent=True)
    if not isinstance(body,dict):abort(400)
    if any(not isinstance(body.get(k),str) or len(body[k])>4096 for k in ('root_id','key')) or not isinstance(body.get('title',''),str):abort(400)
    if body['root_id'].startswith('__'):abort(400)
    try:value=register(body.get('root_id'),body.get('key'),body.get('title',''))
    except (ValueError,OSError,RuntimeError) as e:abort(400,description=str(e) if isinstance(e,ValueError) else 'Файл недоступен или не является GeoTIFF.')
    return jsonify(result=value),201


@data_import_blueprint.post('/imports/files')
def upload_original(field_name='file'):
    editor();request.max_content_length=int(os.environ.get('IMPORT_WEB_MAX_BYTES',str(2*1024**3)))
    file=request.files.get(field_name)
    if not file or Path(file.filename or '').suffix.lower() not in {'.tif','.tiff'}:abort(400)
    root=jobs.staging_root();root.mkdir(parents=True,exist_ok=True);key=str(uuid4())+'.tif';path=root/key;saved=False
    try:
        with path.open('xb') as target:
            while True:
                chunk=file.stream.read(8*1024*1024)
                if not chunk:break
                target.write(chunk)
            target.flush();os.fsync(target.fileno())
        result=register('__uploads',key,request.form.get('title') or file.filename or '');saved=True
        return jsonify(result=result),201
    except (ValueError,RuntimeError) as e:abort(400,description=str(e))
    finally:
        if not saved:path.unlink(missing_ok=True)


@data_import_blueprint.post('/imports/rasters/<int:ortho_id>/prepare')
def prepare(ortho_id):
    editor()
    with Database().cursor() as c:
        c.execute('SELECT asset,projection_id FROM raster_sources WHERE ortho_id=%s',(ortho_id,));row=c.fetchone()
    if not row:abort(404)
    source=row['asset']['source']
    with Database().cursor() as c:
        c.execute('SELECT definition FROM coordinate_systems WHERE id=%s',(row['projection_id'],));projection=c.fetchone()
    if not projection or not projection['definition']:abort(422,description='Сначала задайте определение проекции в разделе «Проекции».')
    try:job=jobs.enqueue(g.current_user_id,source['root_id'],source['key'],title=f'ОФП {ortho_id} · COG',crs_id=row['projection_id'],idempotency_key='prepare:'+str(ortho_id)+':'+hashlib.sha256(projection['definition'].encode()).hexdigest(),internal=True)
    except (ValueError,OSError) as e:abort(400,description=str(e))
    return jsonify(job=jobs.serialize(job)),202


@data_import_blueprint.get('/imports/registered')
def registered():
    editor()
    with Database().cursor() as c:
        c.execute('''SELECT s.ortho_id,o.filename,s.projection_id,s.warning,o.is_cog
            FROM raster_sources s JOIN orthophotos o ON o.id=s.ortho_id ORDER BY s.ortho_id DESC LIMIT 100''');rows=c.fetchall()
    return jsonify(items=rows)


@data_import_blueprint.get('/system/logs')
def system_logs():
    if g.current_user['role']!='admin':abort(403)
    with Database().cursor() as c:
        c.execute('SELECT at,service,level,message FROM system_events ORDER BY id DESC LIMIT 200');events=c.fetchall()
    from pathlib import Path
    import config
    path=Path(config.MEDIA_ROOT).parent/'logs'/'services.json'
    try:
        if path.stat().st_size>4*1024*1024:raise ValueError('Log snapshot is too large')
        snapshot=json.loads(path.read_text())
    except (OSError,ValueError):snapshot={'entries':[],'collected_at':None}
    return jsonify(events=events,services=snapshot.get('entries',[])[:1000],collected_at=snapshot.get('collected_at'))
