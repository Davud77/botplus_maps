from flask import Blueprint, jsonify
import psycopg2
import json
import os
from minio import Minio
from datetime import timedelta

get_ortho_blueprint = Blueprint('get_ortho', __name__)

def load_config(filename):
    dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    config_path = os.path.join(dir_path, filename)
    with open(config_path, 'r') as file:
        return json.load(file)

db_config = load_config('db_config.json')
minio_config = load_config('minio_config.json')

minio_client = Minio(
    minio_config['url'].split('//')[1],
    access_key=minio_config['accessKey'],
    secret_key=minio_config['secretKey'],
    secure=minio_config['url'].startswith('https')
)

def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )

def create_presigned_url(bucket, object_name):
    try:
        return minio_client.presigned_get_object(bucket, object_name, expires=timedelta(hours=12))
    except Exception as e:
        print("Ошибка при создании подписанного URL:", e)
        return None

@get_ortho_blueprint.route('/orthophotos', methods=['GET'])
def get_orthophotos():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, filename, bounds FROM ortholist")
        records = cursor.fetchall()
        orthophotos = [
            {
                'id': row[0],
                'url': create_presigned_url('orthophoto', 'orthophoto/' + row[1]),
                'bounds': json.loads(row[2]) if isinstance(row[2], str) else row[2]
            }
            for row in records
        ]
        return jsonify(orthophotos)
    except Exception as e:
        print(f"Ошибка при получении данных об ортофотопланах: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
