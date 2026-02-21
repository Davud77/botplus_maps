# server/controllers/vector.py
from flask import Blueprint, request, jsonify, make_response
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import math
import xml.etree.ElementTree as ET
import config  # [NEW] Импортируем конфигурацию для доступа к .env

vector_bp = Blueprint('vector', __name__)

# --- ПОДКЛЮЧЕНИЕ К БД (ЧЕРЕЗ PGBOUNCER) ---
def get_db_connection(dbname=None):
    host = os.environ.get('DB_HOST', 'pgbouncer')
    port = os.environ.get('DB_PORT', '6432')
    user = os.environ.get('DB_USER', 'botplus_user')
    password = os.environ.get('DB_PASSWORD', 'botplus_password')
    
    target_db = dbname if dbname else 'postgres'

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=target_db
        )
        return conn
    except Exception as e:
        print(f"!!! DB Connection Error to {target_db}: {e}")
        return None

def release_db_connection(conn, dbname=None):
    try:
        if conn:
            conn.close()
    except:
        pass

# --- Вспомогательная функция: Расчет границ тайла (Web Mercator) ---
def tile_bounds(z, x, y):
    MAX_EXTENT = 20037508.342789244
    tile_size = 2 * MAX_EXTENT / (2 ** z)
    min_x = -MAX_EXTENT + x * tile_size
    max_y = MAX_EXTENT - y * tile_size
    max_x = min_x + tile_size
    min_y = max_y - tile_size
    return min_x, min_y, max_x, max_y

# --- 1. Список баз ---
@vector_bp.route('/vector/databases', methods=['GET'])
def list_databases():
    conn = None
    try:
        conn = get_db_connection('postgres')
        if not conn: return jsonify({'error': 'Connection failed'}), 500
            
        cur = conn.cursor()
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';")
        dbs = cur.fetchall()
        
        # [UPDATED] Берем хост и порт из конфигурации (.env) вместо жестко заданных значений
        host = getattr(config, "DB_HOST", "pgbouncer")
        port = int(getattr(config, "DB_PORT", "6432"))
        
        results = [{'id': n, 'name': n, 'host': host, 'port': port, 'status': 'connected', 'type': 'internal'} for (n,) in dbs]
        cur.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, 'postgres')

# --- 2. Создать базу ---
@vector_bp.route('/vector/create_db', methods=['POST'])
def create_database():
    data = request.json
    new_db_name = data.get('name')
    if not new_db_name or not new_db_name.isalnum():
        return jsonify({'error': 'Invalid database name'}), 400

    conn = None
    conn_new = None
    try:
        conn = get_db_connection('postgres')
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db_name)))
        cur.close()
        release_db_connection(conn, 'postgres')
        conn = None 
        
        conn_new = get_db_connection(new_db_name)
        if not conn_new: return jsonify({'error': 'Connection to new DB failed'}), 500
        
        conn_new.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur_new = conn_new.cursor()
        cur_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur_new.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, 'postgres')
        if conn_new: release_db_connection(conn_new, new_db_name)

# --- 3. Список слоев ---
@vector_bp.route('/vector/layers/<db_name>', methods=['GET'])
def list_layers(db_name):
    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT f_table_schema, f_table_name, type, srid 
                FROM geometry_columns;
            """)
            rows = cur.fetchall()
        except:
            conn.rollback()
            return jsonify([]) 
        
        layers = []
        for row in rows:
            schema, table, geom_type, srid = row
            count = 0
            try:
                full_table_name = f'{schema}.{table}'
                cur.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", (full_table_name,))
                count_res = cur.fetchone()
                count = count_res[0] if count_res else 0
            except Exception as e:
                conn.rollback()
                count = 0
            
            layers.append({
                'id': f"{schema}.{table}",
                'schema': schema,
                'tableName': table,
                'geometryType': geom_type,
                'featureCount': count,
                'srid': srid
            })
        cur.close()
        return jsonify(layers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, db_name)

# --- 4. Создать слой ---
@vector_bp.route('/vector/layers/create', methods=['POST'])
def create_layer():
    data = request.json
    db_name = data.get('dbName')
    table_name = data.get('tableName')
    geom_type = data.get('geomType')
    schema = data.get('schema', 'public')

    if not all([db_name, table_name, geom_type]): return jsonify({'error': 'Missing params'}), 400

    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(sql.SQL("CREATE TABLE {}.{} (id SERIAL PRIMARY KEY, properties JSONB);").format(
            sql.Identifier(schema), sql.Identifier(table_name)
        ))
        cur.execute("SELECT AddGeometryColumn(%s, %s, 'geom', 4326, %s, 2);", (schema, table_name, geom_type.upper()))
        cur.execute(sql.SQL("CREATE INDEX ON {}.{} USING GIST (geom);").format(sql.Identifier(schema), sql.Identifier(table_name)))
        
        cur.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, db_name)

# --- 5. GeoJSON API ---
@vector_bp.route('/vector/layers/<db_name>/<table_name>/data', methods=['GET'])
def get_layer_data(db_name, table_name):
    schema = request.args.get('schema', 'public')
    min_lng = request.args.get('min_lng')
    min_lat = request.args.get('min_lat')
    max_lng = request.args.get('max_lng')
    max_lat = request.args.get('max_lat')
    limit = request.args.get('limit', 5000)

    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("SELECT f_geometry_column, srid FROM geometry_columns WHERE f_table_schema=%s AND f_table_name=%s", (schema, table_name))
        res = cur.fetchone()
        
        if res:
            geom_col, srid = res
        else:
            geom_col, srid = 'geom', 4326 
        
        if srid == 4326:
            bbox_filter = "t.{} && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
        else:
            bbox_filter = "t.{} && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), {})".format("{}", srid)

        query_str = """
            SELECT json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(
                    ST_SimplifyPreserveTopology(
                        ST_Force2D(ST_MakeValid(t.{geom})), 
                        0.00001
                    )
                )::json,
                'properties', to_jsonb(t) - '{geom}'
            ) FROM {schema}.{table} AS t
        """
        
        params = []
        if all([min_lng, min_lat, max_lng, max_lat]):
            query_str += " WHERE " + bbox_filter.format(geom_col)
            params = [min_lng, min_lat, max_lng, max_lat]
        
        query_str += " LIMIT %s"
        params.append(limit)

        formatted_sql = sql.SQL(query_str).format(
            geom=sql.Identifier(geom_col),
            schema=sql.Identifier(schema),
            table=sql.Identifier(table_name)
        )
        
        cur.execute(formatted_sql, params)
        features = [row[0] for row in cur.fetchall()]
        
        cur.close()
        return jsonify({"type": "FeatureCollection", "features": features})
    except Exception as e:
        print(f"GeoJSON Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, db_name)

# --- 6. SINGLE VECTOR TILE (MVT) ---
@vector_bp.route('/vector/tiles/<db_name>/<schema>/<table_name>/<int:z>/<int:x>/<int:y>.pbf', methods=['GET'])
def get_vector_tile(db_name, schema, table_name, z, x, y):
    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        cur = conn.cursor()

        cur.execute(
            "SELECT f_geometry_column, srid FROM geometry_columns WHERE f_table_schema=%s AND f_table_name=%s",
            (schema, table_name)
        )
        res = cur.fetchone()
        
        if not res:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = %s AND table_name = %s 
                AND udt_name = 'geometry'
            """, (schema, table_name))
            res_col = cur.fetchone()
            if not res_col:
                return jsonify({'error': 'Layer geometry not found'}), 404
            geom_col = res_col[0]
            srid = 4326
        else:
            geom_col, srid = res
            if not srid or srid == 0: srid = 4326

        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s AND table_name = %s AND column_name != %s
        """, (schema, table_name, geom_col))
        
        attr_columns = [row[0] for row in cur.fetchall()]
        attrs_select = sql.SQL(", {}").format(sql.SQL(', ').join(map(sql.Identifier, attr_columns))) if attr_columns else sql.SQL("")

        min_x, min_y, max_x, max_y = tile_bounds(z, x, y)

        query = sql.SQL("""
            WITH bounds AS (
                SELECT ST_MakeEnvelope(%s, %s, %s, %s, 3857) AS geom
            ),
            mvtgeom AS (
                SELECT 
                    ST_AsMVTGeom(
                        ST_Transform(ST_Force2D(t.{geom_col}), 3857), 
                        bounds.geom
                    ) AS geom
                    {attrs}
                FROM {schema}.{table} t, bounds
                WHERE 
                    t.{geom_col} && ST_Transform(bounds.geom, %s)
            )
            SELECT ST_AsMVT(mvtgeom.*, %s) FROM mvtgeom
        """).format(
            geom_col=sql.Identifier(geom_col),
            attrs=attrs_select,
            schema=sql.Identifier(schema),
            table=sql.Identifier(table_name)
        )

        cur.execute(query, (min_x, min_y, max_x, max_y, srid, table_name))
        mvt = cur.fetchone()[0]
        cur.close()

        if not mvt:
            return b'', 204

        response = make_response(bytes(mvt))
        response.headers['Content-Type'] = 'application/vnd.mapbox-vector-tile'
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response

    except Exception as e:
        print(f"!!! MVT Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, db_name)

# --- 7. COMBINED VECTOR TILES ---
@vector_bp.route('/vector/tiles/combined/<db_name>/<int:z>/<int:x>/<int:y>.pbf', methods=['GET'])
def get_combined_tiles(db_name, z, x, y):
    layers_param = request.args.get('layers', '')
    schema = request.args.get('schema', 'public')
    
    table_names = [t.strip() for t in layers_param.split(',') if t.strip()]
    if not table_names:
        return b'', 204

    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT f_table_name, f_geometry_column, srid 
            FROM geometry_columns 
            WHERE f_table_schema = %s AND f_table_name = ANY(%s)
        """, (schema, table_names))
        
        meta_rows = cur.fetchall()
        meta_dict = {
            row[0]: {'col': row[1], 'srid': row[2] if row[2] > 0 else 4326} 
            for row in meta_rows
        }

        cur.execute("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s AND table_name = ANY(%s)
        """, (schema, table_names))
        
        attr_rows = cur.fetchall()
        attr_dict = {}
        for t_name, c_name in attr_rows:
            if t_name not in attr_dict:
                attr_dict[t_name] = []
            attr_dict[t_name].append(c_name)
        
        min_x, min_y, max_x, max_y = tile_bounds(z, x, y)
        
        subqueries = []
        params = []
        
        for tbl in table_names:
            if tbl not in meta_dict:
                continue
                
            geom_col = meta_dict[tbl]['col']
            srid = meta_dict[tbl]['srid']
            
            all_cols = attr_dict.get(tbl, [])
            valid_cols = [c for c in all_cols if c != geom_col]
            
            if valid_cols:
                cols_select = sql.SQL(', ') + sql.SQL(', ').join(map(sql.Identifier, valid_cols))
            else:
                cols_select = sql.SQL('')
            
            sq = sql.SQL("""
                COALESCE(
                    (
                        SELECT ST_AsMVT(mvtgeom.*, {layer_name_literal}) 
                        FROM (
                            SELECT 
                                ST_AsMVTGeom(
                                    ST_Transform(ST_Force2D(t.{geom_col_id}), 3857), 
                                    ST_MakeEnvelope(%s, %s, %s, %s, 3857)
                                ) AS geom
                                {cols_select}
                            FROM {schema_id}.{table_id} t
                            WHERE 
                                t.{geom_col_id} && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3857), {srid_literal})
                        ) as mvtgeom
                    ), 
                    ''::bytea
                )
            """).format(
                layer_name_literal=sql.Literal(tbl),
                geom_col_id=sql.Identifier(geom_col),
                schema_id=sql.Identifier(schema),
                table_id=sql.Identifier(tbl),
                srid_literal=sql.Literal(srid),
                cols_select=cols_select
            )
            
            subqueries.append(sq)
            params.extend([min_x, min_y, max_x, max_y, min_x, min_y, max_x, max_y])

        if not subqueries:
            return b'', 204

        final_query = sql.SQL("SELECT ") + sql.SQL(" || ").join(subqueries) + sql.SQL(" AS full_mvt")
        
        cur.execute(final_query, params)
        row = cur.fetchone()
        
        full_mvt = row[0] if row else None
        cur.close()

        if not full_mvt:
            return b'', 204

        response = make_response(bytes(full_mvt))
        response.headers['Content-Type'] = 'application/vnd.mapbox-vector-tile'
        response.headers['Cache-Control'] = 'public, max-age=86400'
        
        return response

    except Exception as e:
        print(f"!!! Combined MVT Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        release_db_connection(conn, db_name)

# --- 8. ЭНДПОИНТ ДЛЯ ПОЛУЧЕНИЯ СТИЛЯ (ПОДДЕРЖКА CATEGORIZED) ---
@vector_bp.route('/vector/styles/<db_name>/<schema>/<table_name>', methods=['GET'])
def get_layer_style(db_name, schema, table_name):
    conn = None
    try:
        conn = get_db_connection(db_name)
        if not conn: return jsonify({'error': 'Connection failed'}), 500
        
        cur = conn.cursor()
        
        # Получаем QML XML из БД
        cur.execute("""
            SELECT styleqml FROM public.layer_styles 
            WHERE LOWER(f_table_schema) = LOWER(%s) AND LOWER(f_table_name) = LOWER(%s)
            ORDER BY update_time DESC LIMIT 1
        """, (schema, table_name))
        
        row = cur.fetchone()
        
        # Вспомогательный парсер одного символа
        def extract_symbol_style(symbol_elem):
            if symbol_elem is None: return {'color': '#3388ff'}
            
            props = {prop.get('k'): prop.get('v') for prop in symbol_elem.findall(".//prop")}
            
            style = {
                'weight': 1,
                'fillOpacity': 0.4,
                'fill': True,
                'color': '#3388ff' # fallback
            }
            
            # Цвет
            raw_color = props.get('color') or props.get('outline_color') or props.get('line_color')
            if raw_color:
                c = raw_color.split(',')
                if len(c) >= 3:
                    hex_color = '#%02x%02x%02x' % (int(c[0]), int(c[1]), int(c[2]))
                    style['color'] = hex_color
                    style['fillColor'] = hex_color
                    if len(c) == 4:
                        style['fillOpacity'] = round(int(c[3]) / 255, 2)
            
            # Толщина
            width = props.get('outline_width') or props.get('line_width') or props.get('width')
            if width:
                try: style['weight'] = float(width)
                except: pass
                
            return style

        # Если стиля нет в БД — возвращаем дефолт
        if not row or not row[0]:
            return jsonify({
                'type': 'single',
                'style': {'color': '#3388ff', 'weight': 1, 'fillOpacity': 0.4}
            })
            
        qml_content = str(row[0])
        root = ET.fromstring(qml_content)
        renderer = root.find("renderer-v2")

        if not renderer:
             return jsonify({'type': 'single', 'style': {'color': 'gray'}})

        renderer_type = renderer.get("type")

        # --- ЛОГИКА ДЛЯ КАТЕГОРИЙ (Categorized) ---
        if renderer_type == "categorizedSymbol":
            attr = renderer.get("attr") # Поле классификации
            categories = []
            
            # Парсим каждую категорию
            for cat in renderer.findall("categories/category"):
                value = cat.get("value")
                # label = cat.get("label") # Можно добавить в будущем для легенды
                symbol_name = cat.get("symbol")
                
                # Ищем определение символа по имени
                symbol_node = renderer.find(f"symbols/symbol[@name='{symbol_name}']")
                if symbol_node:
                    style_obj = extract_symbol_style(symbol_node)
                    categories.append({
                        'value': value,
                        'style': style_obj
                    })
            
            return jsonify({
                'type': 'categorized',
                'field': attr,
                'rules': categories
            })

        # --- ЛОГИКА ДЛЯ ОБЫЧНОГО СТИЛЯ (Single) ---
        else:
            symbol = renderer.find("symbols/symbol")
            style_data = extract_symbol_style(symbol)
            return jsonify({
                'type': 'single',
                'style': style_data
            })

    except Exception as e:
        print(f"!!! Style Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, db_name)