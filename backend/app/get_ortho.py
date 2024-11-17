from flask import Blueprint, jsonify
import psycopg2
import os
from minio import Minio
from datetime import timedelta

get_ortho_blueprint = Blueprint('get_ortho', __name__)

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