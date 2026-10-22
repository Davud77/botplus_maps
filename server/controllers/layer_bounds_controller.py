"""Small WGS84 footprints for navigation; geometry stays on the server."""
import math
from flask import Blueprint, jsonify, request, abort
from psycopg2 import sql, errors
try:
    from ..database import Database
except ImportError:
    from database import Database

bounds_blueprint = Blueprint('layer_bounds', __name__)
database = Database(statement_timeout_ms=3000)


@bounds_blueprint.get('/layers/bounds')
def layer_bounds():
    kind = request.args.get('kind')
    if kind == 'panoramas':
        db_name, schema, table = None, 'public', 'photos_4326'
    elif kind == 'vector':
        db_name = request.args.get('dbName')
        schema = request.args.get('schema')
        table = request.args.get('tableName')
        if not all(isinstance(v, str) and 0 < len(v) <= 63 for v in (db_name, schema, table)):
            abort(400, description='Укажите векторный слой.')
    else:
        abort(400, description='Неизвестный тип слоя.')
    try:
        with database.cursor(database_name=db_name) as cur:
            cur.execute('''SELECT f_geometry_column, srid FROM geometry_columns
                WHERE f_table_schema=%s AND f_table_name=%s''', (schema, table))
            geometry = cur.fetchone()
            if not geometry:
                abort(404, description='Слой не найден.')
            srid, column = geometry['srid'], geometry['f_geometry_column']
            if not srid:
                abort(422, description='У слоя не задана исходная система координат.')
            # Statistics avoid scanning millions of geometries on every click.
            cur.execute('SELECT ST_EstimatedExtent(%s,%s,%s) AS extent', (schema, table, column))
            extent = cur.fetchone()['extent']
            estimated = extent is not None
            if extent is None:
                # New/small layers may not have ANALYZE statistics yet. This
                # fallback is read-only and bounded by the transaction timeout.
                cur.execute(sql.SQL('SELECT ST_Extent({}) AS extent FROM {}.{}').format(
                    sql.Identifier(column), sql.Identifier(schema), sql.Identifier(table)))
                extent = cur.fetchone()['extent']
            if extent is None:
                return jsonify(bounds=None, estimated=False)
            cur.execute('''WITH b AS (SELECT ST_Transform(ST_SetSRID(%s::box2d::geometry,%s),4326) AS geom)
                SELECT ST_XMin(geom) AS west,ST_YMin(geom) AS south,
                       ST_XMax(geom) AS east,ST_YMax(geom) AS north FROM b''', (extent, srid))
            bounds = dict(cur.fetchone())
            if not all(v is not None and math.isfinite(v) for v in bounds.values()):
                abort(422, description='Не удалось определить границы слоя.')
        return jsonify(bounds=bounds, estimated=estimated)
    except errors.QueryCanceled:
        return jsonify(message='Границы пока недоступны. Обновите статистику слоя (ANALYZE) и повторите.'), 503
