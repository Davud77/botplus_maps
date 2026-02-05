from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

vector_bp = Blueprint('vector', __name__)

# --- Вспомогательная функция для получения соединения ---
def get_db_connection(db_params):
    """Создает подключение к указанной базе данных."""
    conn = psycopg2.connect(
        host=db_params.get('host', 'db'),
        port=db_params.get('port', 5432),
        user=db_params.get('user', 'botplus_user'),
        password=db_params.get('password', 'botplus_password'),
        dbname=db_params.get('dbname', 'postgres')
    )
    return conn

# --- 1. Получить список подключенных баз ---
@vector_bp.route('/vector/databases', methods=['GET'])
def list_databases():
    results = []
    
    # 1. Добавляем "Локальный PostGIS"
    try:
        conn = get_db_connection({'dbname': 'postgres'})
        cur = conn.cursor()
        
        # Исключаем системные базы и шаблоны
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';")
        dbs = cur.fetchall()
        
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
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify(results)

# --- 2. Создать новую базу данных ---
@vector_bp.route('/vector/create_db', methods=['POST'])
def create_database():
    data = request.json
    new_db_name = data.get('name')
    
    if not new_db_name:
        return jsonify({'error': 'No database name provided'}), 400

    # Строгая проверка имени БД при создании
    if not new_db_name.isalnum():
        return jsonify({'error': 'Database name must be alphanumeric'}), 400

    try:
        conn = get_db_connection({'dbname': 'postgres'})
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Безопасное создание БД
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db_name)))
        
        cur.close()
        conn.close()
        
        # Подключаем PostGIS в новой базе
        conn_new = get_db_connection({'dbname': new_db_name})
        conn_new.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur_new = conn_new.cursor()
        cur_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur_new.close()
        conn_new.close()
        
        return jsonify({'status': 'ok', 'message': f'Database {new_db_name} created with PostGIS'})
        
    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 3. Получить слои из конкретной базы (С поддержкой SCHEMAS) ---
@vector_bp.route('/vector/layers/<db_name>', methods=['GET'])
def list_layers(db_name):
    try:
        conn = get_db_connection({'dbname': db_name})
        cur = conn.cursor()
        
        # Проверяем наличие PostGIS
        try:
            # Запрашиваем ВСЕ схемы (f_table_schema), не только public
            query = """
                SELECT f_table_schema, f_table_name, type, srid 
                FROM geometry_columns;
            """
            cur.execute(query)
            rows = cur.fetchall()
        except psycopg2.errors.UndefinedTable:
            # Если PostGIS не установлен, возвращаем пустой список
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify([]) 
        
        layers = []
        for idx, row in enumerate(rows):
            schema_name, table_name, geom_type, srid = row
            
            # Считаем объекты, учитывая схему и название таблицы
            try:
                count_query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name)
                )
                cur.execute(count_query)
                count = cur.fetchone()[0]
            except:
                conn.rollback()
                count = 0
            
            layers.append({
                'id': idx + 1,
                'schema': schema_name,   # Важно: возвращаем имя схемы
                'tableName': table_name,
                'geometryType': geom_type,
                'featureCount': count,
                'srid': srid
            })
            
        cur.close()
        conn.close()
        
        return jsonify(layers)
        
    except psycopg2.OperationalError:
        return jsonify({'error': 'Database connection failed'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 4. Создать новый слой ---
@vector_bp.route('/vector/layers/create', methods=['POST'])
def create_layer():
    data = request.json
    db_name = data.get('dbName')
    table_name = data.get('tableName')
    geom_type = data.get('geomType')
    # Опционально можно передать schema, пока дефолт 'public'
    schema_name = data.get('schema', 'public')

    if not all([db_name, table_name, geom_type]):
        return jsonify({'error': 'Missing parameters'}), 400

    # Разрешаем создавать таблицы только с безопасными именами
    if not table_name.isidentifier():
        return jsonify({'error': 'Invalid table name (use only alphanumeric and underscore)'}), 400
    
    valid_types = ['POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON']
    if geom_type.upper() not in valid_types:
        return jsonify({'error': 'Invalid geometry type'}), 400

    try:
        conn = get_db_connection({'dbname': db_name})
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Создаем таблицу в указанной схеме (по дефолту public)
        cur.execute(sql.SQL("""
            CREATE TABLE {}.{} (
                id SERIAL PRIMARY KEY,
                name TEXT,
                properties JSONB DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """).format(sql.Identifier(schema_name), sql.Identifier(table_name)))

        # Добавляем геометрию. AddGeometryColumn требует (schema, table, column, srid, type, dim)
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
        conn.close()

        return jsonify({'status': 'ok', 'message': f'Layer {schema_name}.{table_name} ({geom_type}) created'})

    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 5. Получить данные слоя (GeoJSON) ---
@vector_bp.route('/vector/layers/<db_name>/<table_name>/data', methods=['GET'])
def get_layer_data(db_name, table_name):
    # Получаем схему из query string, если не задана - public
    schema_name = request.args.get('schema', 'public')
    
    try:
        conn = get_db_connection({'dbname': db_name})
        cur = conn.cursor()

        # Используем sql.Identifier для поддержки любых имен таблиц и схем.
        # Динамически собираем JSON свойств через to_jsonb(t) - 'geom'.
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
        conn.close()
        return jsonify(feature_collection)

    except psycopg2.Error as e:
        return jsonify({'error': f"SQL Error: {e.pgerror}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500