from flask import Blueprint, jsonify, request
import psycopg2
import json
import os
from minio import Minio
from datetime import timedelta

pano_info_blueprint = Blueprint('pano_info', __name__)

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

@pano_info_blueprint.route('/panorama_info', methods=['GET'])
def get_panorama_info():
    pano_id = request.args.get('id')
    if not pano_id:
        return jsonify({'error': 'Missing id parameter'}), 400
    
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, filename, latitude, longitude, tags, upload_date, user_id, file_size, file_type,
                   full_pano_width_pixels, full_pano_height_pixels, first_photo_date, model, gps_altitude, fov
            FROM panolist
            WHERE id = %s
        """, (pano_id,))
        record = cursor.fetchone()
        if record:
            panorama = {
                'id': record[0],
                'filename': create_presigned_url('pano', 'pano/' + record[1]),
                'latitude': record[2],
                'longitude': record[3],
                'tags': record[4],
                'upload_date': record[5],
                'user_id': record[6],
                'file_size': record[7],
                'file_type': record[8],
                'full_pano_width_pixels': record[9],
                'full_pano_height_pixels': record[10],
                'first_photo_date': record[11],
                'model': record[12],
                'gps_altitude': record[13],
                'fov': record[14]
            }
            return jsonify(panorama)
        else:
            return jsonify({'error': 'Panorama not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
