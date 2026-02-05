from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2 import sql, pool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

vector_bp = Blueprint('vector', __name__)

# --- НАСТРОЙКА ПУЛА СОЕДИНЕНИЙ ---
# Создаем пул к базе 'postgres' для системных операций.
# Для пользовательских баз будем создавать отдельные соединения, 
# так как пул привязан к одной конкретной БД.
try:
    pg_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20, # minconn, maxconn
        host=os.environ.get('DB_HOST', 'db'),
        port=5432,
        user=os.environ.get('DB_USER', 'botplus_user'),
        password=os.environ.get('DB_PASSWORD', 'botplus_password'),
        dbname='postgres'
    )
except Exception as e:
    print(f"Error creating connection pool: {e}")
    pg_pool = None

def get_db_connection(dbname=None):
    """
    Получает соединение.
    Если нужна база 'postgres', берет из пула.
    Если другая база - создает новое соединение.
    """
    # Используем пул только для дефолтной базы
    if pg_pool and (dbname is None or dbname == 'postgres'):
        return pg_pool.getconn()
    
    # Для остальных баз создаем прямое соединение
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'db'),
        port=5432,
        user=os.environ.get('DB_USER', 'botplus_user'),
        password=os.environ.get('DB_PASSWORD', 'botplus_password'),
        dbname=dbname if dbname else 'postgres'
    )

def release_db_connection(conn, dbname=None):
    """Возвращает соединение в пул или закрывает его"""
    if pg_pool and (dbname is None or dbname == 'postgres'):
        pg_pool.putconn(conn)
    else:
        # Если соединение было создано напрямую, закрываем его
        conn.close()

# --- 1. Получить список подключенных баз ---
@vector_bp.route('/vector/databases', methods=['GET'])
def list_databases():
    conn = None
    try:
        conn = get_db_connection('postgres')
        cur = conn.cursor()
        
        # Исключаем системные базы и шаблоны
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';")
        dbs = cur.fetchall()
        
        results = []
        for (db_name,) in dbs:
            results.append({
                'id': db_name, 
                'name': db_name,
                'host': 'localhost (docker)',
                'port': 5432,
                'status': 'connected',
                'type': 'internal'
            })
            
        cur.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, 'postgres')

# --- 2. Создать новую базу данных ---
@vector_bp.route('/vector/create_db', methods=['POST'])
def create_database():
    data = request.json
    new_db_name = data.get('name')
    
    if not new_db_name:
        return jsonify({'error': 'No database name provided'}), 400

    if not new_db_name.isalnum():
        return jsonify({'error': 'Database name must be alphanumeric'}), 400

    conn = None
    conn_new = None
    try:
        # 1. Создаем базу (через postgres conn)
        conn = get_db_connection('postgres')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db_name)))
        cur.close()
        
        # Возвращаем системное соединение в пул перед открытием нового,
        # чтобы не занимать слот, если пул маленький
        release_db_connection(conn, 'postgres')
        conn = None 
        
        # 2. Подключаем PostGIS в новой базе
        conn_new = get_db_connection(new_db_name)
        conn_new.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur_new = conn_new.cursor()
        cur_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur_new.close()
        
        return jsonify({'status': 'ok', 'message': f'Database {new_db_name} created with PostGIS'})
        
    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, 'postgres')
        if conn_new: release_db_connection(conn_new, new_db_name)

# --- 3. Получить слои из конкретной базы (С поддержкой SCHEMAS) ---
@vector_bp.route('/vector/layers/<db_name>', methods=['GET'])
def list_layers(db_name):
    conn = None
    try:
        conn = get_db_connection(db_name)
        cur = conn.cursor()
        
        # Проверяем наличие PostGIS
        try:
            # Запрашиваем ВСЕ схемы (f_table_schema)
            query = """
                SELECT f_table_schema, f_table_name, type, srid 
                FROM geometry_columns;
            """
            cur.execute(query)
            rows = cur.fetchall()
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            return jsonify([]) 
        
        layers = []
        for row in rows:
            schema_name, table_name, geom_type, srid = row
            
            # Считаем объекты (безопасно, с savepoint)
            count = 0
            try:
                cur.execute("SAVEPOINT count_pt")
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name)
                ))
                count = cur.fetchone()[0]
                cur.execute("RELEASE SAVEPOINT count_pt")
            except:
                cur.execute("ROLLBACK TO SAVEPOINT count_pt")
                count = 0
            
            layers.append({
                'id': f"{schema_name}.{table_name}",
                'schema': schema_name,
                'tableName': table_name,
                'geometryType': geom_type,
                'featureCount': count,
                'srid': srid
            })
            
        cur.close()
        return jsonify(layers)
        
    except psycopg2.OperationalError:
        return jsonify({'error': 'Database connection failed'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, db_name)

# --- 4. Создать новый слой ---
@vector_bp.route('/vector/layers/create', methods=['POST'])
def create_layer():
    data = request.json
    db_name = data.get('dbName')
    table_name = data.get('tableName')
    geom_type = data.get('geomType')
    schema_name = data.get('schema', 'public')

    if not all([db_name, table_name, geom_type]):
        return jsonify({'error': 'Missing parameters'}), 400

    # Разрешаем только безопасные имена для новых таблиц
    if not table_name.isidentifier():
        return jsonify({'error': 'Invalid table name (use only alphanumeric and underscore)'}), 400
    
    valid_types = ['POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON']
    if geom_type.upper() not in valid_types:
        return jsonify({'error': 'Invalid geometry type'}), 400

    conn = None
    try:
        conn = get_db_connection(db_name)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Создаем таблицу
        cur.execute(sql.SQL("""
            CREATE TABLE {}.{} (
                id SERIAL PRIMARY KEY,
                name TEXT,
                properties JSONB DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """).format(sql.Identifier(schema_name), sql.Identifier(table_name)))

        # Добавляем геометрию
        sql_add_geom = "SELECT AddGeometryColumn(%s, %s, 'geom', 4326, %s, 2);"
        cur.execute(sql_add_geom, (schema_name, table_name, geom_type.upper()))

        # Индекс
        index_name = f"idx_{table_name}_geom"
        cur.execute(sql.SQL("CREATE INDEX {} ON {}.{} USING GIST (geom);").format(
            sql.Identifier(index_name),
            sql.Identifier(schema_name),
            sql.Identifier(table_name)
        ))

        cur.close()
        return jsonify({'status': 'ok', 'message': f'Layer {schema_name}.{table_name} ({geom_type}) created'})

    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, db_name)

# --- 5. Получить данные слоя (GeoJSON) ---
@vector_bp.route('/vector/layers/<db_name>/<table_name>/data', methods=['GET'])
def get_layer_data(db_name, table_name):
    # Получаем схему из параметров (default: public)
    schema_name = request.args.get('schema', 'public')
    
    conn = None
    try:
        conn = get_db_connection(db_name)
        cur = conn.cursor()

        # Динамически собираем JSON
        query = sql.SQL("""
            SELECT json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(t.geom)::json,
                'properties', to_jsonb(t) - 'geom'
            )
            FROM {}.{} AS t;
        """).format(sql.Identifier(schema_name), sql.Identifier(table_name))
        
        cur.execute(query)
        rows = cur.fetchall()

        features = [row[0] for row in rows]
        feature_collection = {
            "type": "FeatureCollection",
            "features": features
        }

        cur.close()
        return jsonify(feature_collection)

    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: release_db_connection(conn, db_name)