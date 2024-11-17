from flask import Blueprint, jsonify
import psycopg2
import psycopg2.extras
import os
from minio import Minio
from datetime import timedelta

pano_info_blueprint = Blueprint('pano_info', __name__)

def connect_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'botplus'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'password')
    )

minio_client = Minio(
    os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
    access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
    secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
    secure=os.environ.get('MINIO_SECURE', 'False').lower() == 'true'
)

def create_presigned_url(bucket, object_name):
    try:
        return minio_client.presigned_get_object(bucket, object_name, expires=timedelta(hours=12))
    except Exception as e:
        print("Ошибка при создании подписанного URL:", e)
        return None

@pano_info_blueprint.route('/pano_info/<int:pano_id>', methods=['GET'])
def get_pano_info(pano_id):
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM panolist WHERE id = %s", (pano_id,))
        record = cursor.fetchone()
        if record:
            pano_info = dict(record)
            pano_info['url'] = create_presigned_url('pano', pano_info['filename'])
            return jsonify(pano_info)
        else:
            return jsonify({'error': 'Panorama not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()