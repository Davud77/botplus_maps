"""Persistent map documents and revocable, read-only published snapshots."""
from copy import deepcopy
import math
import re
from services import map_settings
import secrets
from uuid import uuid4
from flask import Blueprint, jsonify, request, g, abort, current_app, make_response
from psycopg2.extras import Json
from psycopg2 import Error as DatabaseError
from database import Database
from services.permissions import can_edit_map

maps_blueprint = Blueprint('maps', __name__)
DEFAULT_CONFIG = {'view': {'center': [43, 47], 'zoom': 5}, 'base_layer': 'none',
                  'orthophoto_ids': [], 'vector_layers': [], 'show_panoramas': False,
                  'coordinate_system': 'EPSG:4326', 'base_layer_definition': None, 'layer_settings': []}


def body():
    request.max_content_length = 65536
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description='Ожидается объект JSON.')
    return data


def validate_config(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_CONFIG):
        abort(400, description='Неверная конфигурация карты.')
    config = deepcopy(DEFAULT_CONFIG)
    config.update(value)
    view = config['view']
    if not isinstance(view, dict) or set(view) != {'center', 'zoom'}:
        abort(400, description='Неверное положение карты.')
    center, zoom = view['center'], view['zoom']
    numeric = lambda number: type(number) in {int, float} and -1e10 < number < 1e10 and math.isfinite(number)
    if (not isinstance(center, list) or len(center) != 2 or not all(numeric(n) for n in center)
            or not -85.051129 <= center[0] <= 85.051129 or not -180 <= center[1] <= 180
            or not numeric(zoom) or not 0 <= zoom <= 23):
        abort(400, description='Недопустимые координаты или масштаб.')
    if not isinstance(config['base_layer'], str) or type(config['show_panoramas']) is not bool:
        abort(400, description='Неверная подложка карты.')
    definition = map_settings.basemap(config['base_layer'])
    legacy = {'light','dark','osm','none','google_hybrid','google_satellite','google_maps','esri_satellite','esri_streets','esri_topo','voyager','positron','topo','cycle','wikimedia'}
    if not definition and config['base_layer'] not in legacy:
        abort(400, description='Подложка не найдена.')
    config['base_layer_definition'] = definition
    if not isinstance(config['coordinate_system'], str): abort(400)
    map_settings.coordinate_system(config['coordinate_system'])
    orthos, vectors = config['orthophoto_ids'], config['vector_layers']
    if not isinstance(orthos, list) or len(orthos) > 128 or any(type(i) is not int or i <= 0 for i in orthos) or len(set(orthos)) != len(orthos):
        abort(400, description='Выберите не более 128 ортофотопланов.')
    if not isinstance(vectors, list) or len(vectors) > 128:
        abort(400, description='Выберите не более 128 векторных слоёв.')
    for layer in vectors:
        if (not isinstance(layer, dict) or set(layer) != {'dbName', 'schema', 'tableName'}
                or any(not isinstance(v, str) or not 1 <= len(v) <= 63 or '\x00' in v for v in layer.values())):
            abort(400, description='Неверный векторный слой.')
    # A publication may expose only existing geometry layers, never arbitrary SQL tables.
    if orthos:
        with Database().cursor() as cursor:
            cursor.execute('SELECT id FROM orthophotos WHERE id=ANY(%s)', (orthos,))
            if len(cursor.fetchall()) != len(orthos):
                abort(400, description='Ортофотоплан больше не существует.')
    try:
        for layer in vectors:
            with Database().cursor(database_name=layer['dbName']) as cursor:
                cursor.execute('''SELECT 1 FROM information_schema.columns WHERE table_schema=%s
                    AND table_name=%s AND udt_name='geometry' LIMIT 1''', (layer['schema'], layer['tableName']))
                if not cursor.fetchone():
                    abort(400, description='Векторный слой больше не существует.')
    except DatabaseError:
        abort(400, description='Не удалось проверить подключение векторного слоя.')
    allowed = {f'ortho:{i}' for i in orthos} | {f'vector:{i}' for i in range(len(vectors))}
    if config['show_panoramas']: allowed.add('panoramas')
    if config['base_layer'] != 'none': allowed.add('basemap')
    presentations = config['layer_settings']
    if not isinstance(presentations,list) or len(presentations)>258: abort(400)
    seen = set()
    for item in presentations:
        if not isinstance(item,dict) or set(item)-{'key','visible','opacity','style','coordinate_system'}: abort(400)
        key=item.get('key')
        if not isinstance(key,str) or key not in allowed or key in seen: abort(400,description='Неверный список слоёв карты.')
        seen.add(key)
        if 'coordinate_system' in item:
            if not isinstance(item['coordinate_system'],str): abort(400)
            map_settings.coordinate_system(item['coordinate_system'])
        if type(item.get('visible',True)) is not bool or not numeric(item.get('opacity',1)) or not 0<=item.get('opacity',1)<=1: abort(400)
        style=item.get('style',{})
        if not isinstance(style,dict) or set(style)-{'color','weight','fillOpacity','radius'}: abort(400)
        if 'color' in style and (not isinstance(style['color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',style['color'])): abort(400)
        for name,maximum in [('weight',20),('fillOpacity',1),('radius',30)]:
            if name in style and (not numeric(style[name]) or not 0<=style[name]<=maximum): abort(400)
    return config


def title_and_description(data):
    title, description = data.get('title'), data.get('description', '')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120 or not isinstance(description, str) or len(description) > 1000:
        abort(400, description='Название: 1–120 символов, описание: до 1000 символов.')
    return title.strip(), description


def document(map_id, write=False, cursor=None):
    if cursor is None:
        with Database().cursor(write=write) as own:
            return document(map_id, write, own)
    cursor.execute('SELECT * FROM maps WHERE id=%s' + (' FOR UPDATE' if write else ''), (str(map_id),))
    row = cursor.fetchone()
    if not row:
        abort(404, description='Карта не найдена.')
    if write and not can_edit_map(row):
        abort(403, description='Изменять карту может её владелец или администратор.')
    return row


def serialize(row):
    result = dict(row)
    result['id'] = str(result['id'])
    result.pop('published_snapshot', None)
    result['can_edit'] = can_edit_map(row)
    result['published'] = bool(result.get('public_slug'))
    return result


@maps_blueprint.get('/maps')
def list_maps():
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        abort(400)
    query = request.args.get('q', '')[:120]
    mode = request.args.get('status', 'all')
    where = "(title ILIKE %s OR description ILIKE %s)"
    if mode == 'published':
        where += ' AND public_slug IS NOT NULL'
    elif mode == 'private':
        where += ' AND public_slug IS NULL'
    elif mode != 'all':
        abort(400)
    args = ('%' + query + '%',) * 2
    with Database().cursor() as cursor:
        cursor.execute(f'SELECT count(*) AS total FROM maps WHERE {where}', args)
        total = cursor.fetchone()['total']
        cursor.execute(f'''SELECT m.id,m.title,m.description,m.owner_id,m.public_slug,m.updated_at,m.revision,
            u.username AS owner_name FROM maps m JOIN users u ON u.id=m.owner_id
            WHERE {where} ORDER BY m.updated_at DESC,m.id LIMIT 48 OFFSET %s''', (*args, offset))
        rows = cursor.fetchall()
    return jsonify(maps=[serialize(row) for row in rows], total=total)


@maps_blueprint.post('/maps')
def create_map():
    data = body()
    title, description = title_and_description(data)
    defaults = map_settings.settings()['defaults']
    config = validate_config(data.get('config', {'base_layer': defaults['basemap'], 'coordinate_system': defaults['coordinate_system']}))
    with Database().cursor(write=True) as cursor:
        cursor.execute('INSERT INTO maps (id,owner_id,title,description,config) VALUES (%s,%s,%s,%s,%s) RETURNING *',
                       (str(uuid4()), g.current_user_id, title, description, Json(config)))
        row = cursor.fetchone()
    return jsonify(map=serialize(row)), 201


@maps_blueprint.get('/maps/<uuid:map_id>')
def get_map(map_id):
    return jsonify(map=serialize(document(map_id)))


@maps_blueprint.put('/maps/<uuid:map_id>')
def save_map(map_id):
    # Check ownership before catalog validation / other database connections.
    document(map_id, write=True)
    data = body()
    title, description = title_and_description(data)
    if type(data.get('revision')) is not int:
        abort(400, description='Укажите версию карты.')
    config = validate_config(data.get('config', {}))
    with Database().cursor(write=True) as cursor:
        row = document(map_id, True, cursor)
        if data['revision'] != row['revision']:
            return jsonify(message='Карта изменена в другом окне. Обновите страницу перед сохранением.'), 409
        cursor.execute('''UPDATE maps SET title=%s,description=%s,config=%s,revision=revision+1,updated_at=NOW()
            WHERE id=%s RETURNING *''', (title, description, Json(config), str(map_id)))
        row = cursor.fetchone()
    return jsonify(map=serialize(row))


@maps_blueprint.post('/maps/<uuid:map_id>/publication')
def publish_map(map_id):
    data = body()
    if type(data.get('published')) is not bool or type(data.get('revision')) is not int:
        abort(400, description='Укажите состояние публикации и версию карты.')
    with Database().cursor(write=True) as cursor:
        row = document(map_id, True, cursor)
        if data['revision'] != row['revision']:
            return jsonify(message='Версия карты изменилась. Обновите страницу.'), 409
        if data['published'] and row['config']['show_panoramas']:
            return jsonify(message='Публичные панорамы пока не поддерживаются. Отключите слой панорам перед публикацией.'), 400
        snapshot = {'title': row['title'], 'description': row['description'], 'config': row['config']} if data['published'] else None
        slug = (row['public_slug'] or secrets.token_urlsafe(24)) if snapshot else None
        cursor.execute('''UPDATE maps SET public_slug=%s,published_snapshot=%s,revision=revision+1,updated_at=NOW()
            WHERE id=%s RETURNING *''', (slug, Json(snapshot) if snapshot else None, str(map_id)))
        row = cursor.fetchone()
    return jsonify(map=serialize(row))


def publication(slug):
    with Database().cursor() as cursor:
        cursor.execute('SELECT published_snapshot FROM maps WHERE public_slug=%s AND published_snapshot IS NOT NULL', (slug,))
        row = cursor.fetchone()
    if not row:
        abort(404, description='Публикация не найдена или отключена.')
    return row['published_snapshot']


@maps_blueprint.get('/public/maps/<slug>')
def get_public_map(slug):
    snapshot = deepcopy(publication(slug))
    snapshot['config']['vector_layers'] = [{'tableName': layer['tableName']} for layer in snapshot['config']['vector_layers']]
    return jsonify(map=snapshot)


def check_tile(z, x, y):
    if z > 24 or x >= 2**z or y >= 2**z:
        abort(404)


@maps_blueprint.get('/public/maps/<slug>/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>@2x.webp', defaults={'scale':2,'image_format':'webp'})
@maps_blueprint.get('/public/maps/<slug>/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>@2x.png', defaults={'scale':2})
@maps_blueprint.get('/public/maps/<slug>/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>.png')
def public_raster(slug, ortho_id, z, x, y, scale=1, image_format='png'):
    check_tile(z, x, y)
    if ortho_id not in publication(slug)['config']['orthophoto_ids']:
        abort(404)
    if image_format=='webp':return current_app.view_functions['ortho.get_ortho_tile'](ortho_id,z,x,y,scale=scale,image_format=image_format)
    return current_app.view_functions['ortho.get_ortho_tile'](ortho_id, z, x, y, scale=scale) if scale==2 else current_app.view_functions['ortho.get_ortho_tile'](ortho_id, z, x, y)


@maps_blueprint.get('/public/maps/<slug>/vectors/<int:index>/tiles/<int:z>/<int:x>/<int:y>.pbf')
def public_vector(slug, index, z, x, y):
    check_tile(z, x, y)
    layers = publication(slug)['config']['vector_layers']
    if index >= len(layers):
        abort(404)
    layer = layers[index]
    from controllers.vector import get_vector_tile
    response = make_response(get_vector_tile(layer['dbName'], layer['schema'], layer['tableName'], z, x, y))
    if response.status_code >= 500:
        return jsonify(message='Векторный слой временно недоступен.'), 502
    return response


@maps_blueprint.get('/public/maps/<slug>/coordinates/<layer_key>')
def public_coordinates(slug, layer_key):
    config=publication(slug)['config']
    allowed={f'ortho:{i}' for i in config['orthophoto_ids']} | {f'vector:{i}' for i in range(len(config['vector_layers']))}
    if config['base_layer'] != 'none': allowed.add('basemap')
    if layer_key not in allowed: abort(404)
    item=next((item for item in config.get('layer_settings',[]) if item['key']==layer_key),{})
    from controllers.settings_controller import coordinate_response
    return coordinate_response(item.get('coordinate_system','EPSG:3857' if layer_key=='basemap' else 'EPSG:4326'))
