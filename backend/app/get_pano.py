from flask import Blueprint, jsonify
import psycopg2
import os
from minio import Minio
from datetime import timedelta

pano_blueprint = Blueprint('pano', __name__)

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