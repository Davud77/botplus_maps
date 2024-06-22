from flask import Blueprint, jsonify
import psycopg2
import json
import os
from minio import Minio
from datetime import timedelta

pano_blueprint = Blueprint('pano', __name__)

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

@pano_blueprint.route('/panoramas', methods=['GET'])
def get_panoramas():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, latitude, longitude FROM panolist")
        records = cursor.fetchall()
        panoramas = [
            {
                'id': row[0],
                'latitude': row[1],
                'longitude': row[2]
            }
            for row in records
        ]
        return jsonify(panoramas)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
