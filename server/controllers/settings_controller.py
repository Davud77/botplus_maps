import math
from uuid import uuid4
from flask import Blueprint,request,jsonify,abort,g
from database import Database
from services.permissions import require_admin
from services import map_settings

settings_blueprint=Blueprint('settings',__name__)


def body():
    request.max_content_length=24000
    data=request.get_json(silent=True)
    if not isinstance(data,dict): abort(400,description='Ожидается объект JSON.')
    return data


@settings_blueprint.get('/settings/map')
def get_settings():
    return jsonify(map_settings.settings())


@settings_blueprint.post('/settings/coordinate-systems')
def add_crs():
    require_admin(); data=body()
    name=data.get('name')
    if not isinstance(name,str) or not 1<=len(name.strip())<=120: abort(400,description='Название: 1–120 символов.')
    definition=map_settings.parse_crs(data.get('definition'))
    with Database().cursor(write=True) as cursor:
        cursor.execute('INSERT INTO coordinate_systems (id,name,definition) VALUES (%s,%s,%s) RETURNING *',('custom:'+str(uuid4()),name.strip(),definition))
        row=cursor.fetchone()
    return jsonify(coordinate_system=row),201


@settings_blueprint.post('/settings/basemaps')
def add_basemap():
    require_admin(); data=body()
    values=map_settings.validate_basemap(data)
    with Database().cursor(write=True) as cursor:
        cursor.execute('INSERT INTO basemaps (id,name,url,attribution,scheme,max_zoom) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *',('custom:'+str(uuid4()),*values))
        row=cursor.fetchone()
    return jsonify(basemap=row),201


@settings_blueprint.patch('/settings/map/defaults')
def update_defaults():
    require_admin(); data=body()
    if set(data)-{'coordinate_system','basemap'} or not data: abort(400)
    with Database().cursor(write=True) as cursor:
        cursor.execute('SELECT * FROM map_defaults WHERE id=1 FOR UPDATE'); current=cursor.fetchone()
        crs=data.get('coordinate_system',current['coordinate_system']); basemap=data.get('basemap',current['basemap'])
        if not isinstance(crs,str) or not isinstance(basemap,str): abort(400)
        cursor.execute('SELECT 1 FROM coordinate_systems WHERE id=%s',(crs,))
        if not cursor.fetchone(): abort(400,description='Система координат не найдена.')
        cursor.execute('SELECT 1 FROM basemaps WHERE id=%s',(basemap,))
        if not cursor.fetchone(): abort(400,description='Подложка не найдена.')
        cursor.execute('UPDATE map_defaults SET coordinate_system=%s,basemap=%s WHERE id=1',(crs,basemap))
    return jsonify(status='ok')


@settings_blueprint.patch('/account/preferences')
def preferences():
    data=body()
    if set(data)!={'theme'} or data['theme'] not in ['light','dark']: abort(400,description='Выберите светлую или тёмную тему.')
    with Database().cursor(write=True) as cursor:
        cursor.execute('UPDATE users SET theme=%s WHERE id=%s',(data['theme'],g.current_user_id))
    return jsonify(status='ok',theme=data['theme'])


@settings_blueprint.get('/settings/coordinates')
def transform_coordinates():
    return coordinate_response(request.args.get('crs','EPSG:4326'))


def coordinate_response(code):
    try:
        lat=float(request.args['lat']); lng=float(request.args['lng'])
        if not all(math.isfinite(v) for v in [lat,lng]) or not -85.051129<=lat<=85.051129 or not -180<=lng<=180: raise ValueError()
    except (ValueError,KeyError): abort(400,description='Проверьте координаты.')
    definition=map_settings.coordinate_system(code)
    from osgeo import osr
    try:
        source=osr.SpatialReference(); source.ImportFromEPSG(4326)
        target=osr.SpatialReference(); target.SetFromUserInput(definition['definition'])
        for srs in [source,target]: srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        x,y,_=osr.CoordinateTransformation(source,target).TransformPoint(lng,lat)
        if not all(math.isfinite(v) for v in [x,y]): raise ValueError()
    except Exception: abort(400,description='Не удалось пересчитать координаты в выбранную СК.')
    return jsonify(x=x,y=y,unit='°' if target.IsGeographic() else target.GetLinearUnitsName(),name=definition['name'])
