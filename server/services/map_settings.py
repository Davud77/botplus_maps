"""Installation-owned CRS and basemap catalogs. No remote fetches from definitions."""
from urllib.parse import urlsplit
import re
from html import escape
from flask import abort
from database import Database

BUILTIN_CRS = [('EPSG:4326','WGS 84','EPSG:4326'),('EPSG:3857','Web Mercator','EPSG:3857'),
               ('EPSG:32638','WGS 84 / UTM 38N','EPSG:32638'),('EPSG:32639','WGS 84 / UTM 39N','EPSG:32639')]
BUILTIN_BASEMAPS = [
 ('google_maps','Google · Карта','https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}','© Google'),
 ('google_satellite','Google · Спутник','https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}','© Google'),
 ('google_hybrid','Google · Гибрид','https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}','© Google'),
 ('osm','OpenStreetMap','https://tile.openstreetmap.org/{z}/{x}/{y}.png','© OpenStreetMap contributors'),
 ('none','Без подложки','','')]


def initialize_catalogs(cursor):
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(10) NOT NULL DEFAULT 'light'")
    cursor.execute('''CREATE TABLE IF NOT EXISTS coordinate_systems (
        id TEXT PRIMARY KEY, name VARCHAR(120) NOT NULL, definition TEXT NOT NULL, builtin BOOLEAN NOT NULL DEFAULT FALSE
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS basemaps (
        id TEXT PRIMARY KEY, name VARCHAR(120) NOT NULL, url TEXT NOT NULL, attribution VARCHAR(300) NOT NULL DEFAULT '',
        scheme VARCHAR(3) NOT NULL DEFAULT 'xyz', max_zoom INTEGER NOT NULL DEFAULT 22, builtin BOOLEAN NOT NULL DEFAULT FALSE
    )''')
    for code,name,definition in BUILTIN_CRS:
        cursor.execute('INSERT INTO coordinate_systems (id,name,definition,builtin) VALUES (%s,%s,%s,TRUE) ON CONFLICT DO NOTHING',(code,name,definition))
    for code,name,url,attribution in BUILTIN_BASEMAPS:
        cursor.execute('INSERT INTO basemaps (id,name,url,attribution,builtin) VALUES (%s,%s,%s,%s,TRUE) ON CONFLICT DO NOTHING',(code,name,url,attribution))
    cursor.execute('''CREATE TABLE IF NOT EXISTS map_defaults (
        id INTEGER PRIMARY KEY CHECK(id=1), coordinate_system TEXT NOT NULL REFERENCES coordinate_systems(id),
        basemap TEXT NOT NULL REFERENCES basemaps(id)
    )''')
    cursor.execute("INSERT INTO map_defaults VALUES (1,'EPSG:4326','google_maps') ON CONFLICT DO NOTHING")


def settings():
    with Database().cursor() as cursor:
        cursor.execute('SELECT * FROM coordinate_systems ORDER BY builtin DESC,name')
        crs = cursor.fetchall()
        cursor.execute('SELECT * FROM basemaps ORDER BY builtin DESC,name')
        basemaps = cursor.fetchall()
        cursor.execute('SELECT coordinate_system,basemap FROM map_defaults WHERE id=1')
        defaults = cursor.fetchone()
    return {'coordinate_systems':crs,'basemaps':basemaps,'defaults':defaults}


def coordinate_system(code):
    with Database().cursor() as cursor:
        cursor.execute('SELECT * FROM coordinate_systems WHERE id=%s',(code,))
        row=cursor.fetchone()
    if not row: abort(400,description='Система координат не найдена.')
    return dict(row)


def basemap(code):
    with Database().cursor() as cursor:
        cursor.execute('SELECT id,name,url,attribution,scheme,max_zoom FROM basemaps WHERE id=%s',(code,))
        row=cursor.fetchone()
    return dict(row) if row else None


def parse_crs(definition):
    if not isinstance(definition,str) or not 3 <= len(definition) <= 16000:
        abort(400,description='Укажите EPSG-код, WKT или PROJ-определение до 16000 символов.')
    definition=definition.strip()
    upper=definition.upper()
    prefixes=('GEOGCS[','PROJCS[','GEOGCRS[','PROJCRS[','GEODCRS[','COMPOUNDCRS[','LOCAL_CS[','ENGCRS[','BOUNDCRS[')
    if not (re.fullmatch(r'EPSG:\d{3,7}',upper) or upper.startswith(prefixes) or definition.startswith('+proj=')):
        abort(400,description='Поддерживаются EPSG:код, WKT и строки +proj=…')
    if re.search(r'https?://|file:|/vsi|\.\.|\+init=|\+nadgrids=|\+geoidgrids=',definition,re.I):
        abort(400,description='Ссылки, файловые пути и внешние сетки в определении не поддерживаются.')
    from osgeo import osr
    srs=osr.SpatialReference()
    try:
        result=srs.SetFromUserInput(definition)
        if result != 0 or srs.Validate()!=0: raise ValueError('invalid CRS')
        return srs.ExportToWkt()
    except Exception:
        abort(400,description='GDAL не распознал систему координат. Проверьте определение.')


def validate_basemap(data):
    name,url,attribution=data.get('name'),data.get('url'),data.get('attribution','')
    if not isinstance(name,str) or not 1 <= len(name.strip()) <= 120 or not isinstance(url,str) or not 1 <= len(url) <= 2048 or not isinstance(attribution,str) or len(attribution)>300:
        abort(400,description='Проверьте название, URL и подпись источника.')
    try:
        parsed=urlsplit(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('invalid URL')
        _=parsed.port
    except ValueError:
        abort(400,description='Укажите HTTP(S) URL без логина и пароля в адресе.')
    if re.search(r'[\x00-\x20]',url): abort(400,description='URL не должен содержать пробелы или управляющие символы.')
    if any(token not in url for token in ['{z}','{x}','{y}']) or set(re.findall(r'\{([^{}]*)\}',url)) - {'z','x','y','s','r'} or re.search(r'[{}]',re.sub(r'\{[zxysr]\}', '', url)):
        abort(400,description='URL тайлов должен содержать {z}, {x}, {y}; допустимы также {s} и {r}.')
    if data.get('scheme','xyz') not in ['xyz','tms'] or type(data.get('max_zoom',22)) is not int or not 0<=data.get('max_zoom',22)<=24:
        abort(400,description='Проверьте схему тайлов и максимальный масштаб (0–24).')
    return name.strip(),url,escape(attribution),data.get('scheme','xyz'),data.get('max_zoom',22)
