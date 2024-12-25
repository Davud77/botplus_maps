# file: get_pano_info.py  (или pano_info.py)
from flask import Blueprint, jsonify, send_file
import psycopg2
import psycopg2.extras
import os
from minio import Minio
from datetime import timedelta
import io  # Для работы с бинарными потоками

pano_info_blueprint = Blueprint('pano_info', __name__)

def connect_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'botplus'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'password')
    )

# ВНИМАНИЕ: здесь используем "minio:9000" или что-то аналогичное,
# если код крутится ВНУТРИ контейнера и MinIO тоже в docker-compose.
# Если MinIO достаётся по "localhost:9000" — оставьте localhost,
# но тогда нужно убедиться, что из контейнера есть доступ к localhost:9000.
minio_client = Minio(
    os.environ.get('MINIO_ENDPOINT', 'minio:9000'),  
    access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
    secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
    secure=os.environ.get('MINIO_SECURE', 'False').lower() == 'true'
)

@pano_info_blueprint.route('/pano_info/<int:pano_id>', methods=['GET'])
def get_pano_info(pano_id):
    """
    Возвращает JSON с информацией о конкретной панораме (без URL).
    """
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM panolist WHERE id = %s", (pano_id,))
        record = cursor.fetchone()
        if record:
            pano_info = dict(record)
            # Удаляем поле url (если оно раньше заполнялось).
            # Или можно вернуть имя файла, если нужно на фронтенде.
            pano_info.pop('url', None)
            return jsonify(pano_info)
        else:
            return jsonify({'error': 'Panorama not found'}), 404
    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@pano_info_blueprint.route('/pano_info/<int:pano_id>/download', methods=['GET'])
def download_pano_file(pano_id):
    """
    Возвращает сам файл (картинку панорамы) напрямую через Flask,
    не раскрывая presigned URL. 
    """
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM panolist WHERE id = %s", (pano_id,))
        record = cursor.fetchone()
        if record:
            pano_info = dict(record)
            filename = pano_info['filename']  # "GSAB5464_20221023.JPG" и т.п.
            # Попытаемся скачать объект из MinIO
            try:
                response_obj = minio_client.get_object("pano", filename)
                file_data = response_obj.read()  # Считываем весь файл в память
                response_obj.close()
                response_obj.release_conn()

                # MIME-тип можно взять из базы (file_type) или поставить 'image/jpeg'
                content_type = pano_info.get('file_type') or 'application/octet-stream'
                # Возвращаем как файл
                return send_file(
                    io.BytesIO(file_data),
                    mimetype=content_type,
                    download_name=filename  # Чтобы при скачивании имя файла было реальным
                )
            except Exception as e:
                print(f"Ошибка при скачивании из MinIO: {e}")
                return jsonify({'error': 'Failed to retrieve file from MinIO'}), 500

        else:
            return jsonify({'error': 'Panorama not found'}), 404
    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
