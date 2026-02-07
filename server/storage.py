# server/storage.py
import os
import io
from flask import send_file, send_from_directory, jsonify, abort
from minio import Minio
from minio.error import S3Error

# ==========================================
# 1. LocalStorage (Нужен для OrthoController)
# ==========================================
class LocalStorage:
    """
    Класс для работы с локальной файловой системой.
    Необходим для GDAL/Ortho, так как генерация тайлов требует доступа к диску.
    """
    def __init__(self, root_folder):
        self.root = root_folder
        # Создаем папку, если её нет
        if self.root and not os.path.exists(self.root):
            os.makedirs(self.root, exist_ok=True)

    def save_file(self, file_object, filename):
        """Сохраняет файл из request.files локально"""
        full_path = os.path.join(self.root, filename)
        file_object.save(full_path)
        return full_path

    def send_local_file(self, filename_or_path, mimetype=None):
        """
        Отдает файл. Умеет работать как с именем файла внутри root,
        так и с полным абсолютным путем (нужно для тайлов).
        """
        # Если передан абсолютный путь (как в случае с тайлами в контроллере)
        if os.path.isabs(filename_or_path):
            if not os.path.exists(filename_or_path):
                abort(404)
            directory = os.path.dirname(filename_or_path)
            filename = os.path.basename(filename_or_path)
            return send_from_directory(directory, filename, mimetype=mimetype)
        
        # Иначе берем из корня хранилища (self.root)
        full_path = os.path.join(self.root, filename_or_path)
        if not os.path.exists(full_path):
             abort(404)
             
        return send_from_directory(self.root, filename_or_path, mimetype=mimetype)

    def delete_file(self, filename):
        full_path = os.path.join(self.root, filename)
        if os.path.exists(full_path):
            os.remove(full_path)


# ==========================================
# 2. MinioStorage (Нужен для Panoramas)
# ==========================================
class MinioStorage:
    """
    Класс для работы с S3-хранилищем (MinIO).
    """
    def __init__(self):
        # Получаем настройки из переменных окружения
        self.endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        self.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = os.environ.get("MINIO_BUCKET_NAME", "panoramas")
        # Для локальной разработки secure=False (http), для продакшена True (https)
        self.secure = os.environ.get("MINIO_SECURE", "False").lower() == "true"

        # Инициализация клиента
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            self._ensure_bucket()
        except Exception as e:
            print(f"Warning: Failed to initialize MinIO client. {e}")
            self.client = None

    def _ensure_bucket(self):
        """Создает бакет, если он не существует."""
        if not self.client: return
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created.")
        except S3Error as e:
            print(f"MinIO Error (Ensure Bucket): {e}")
        except Exception as e:
            print(f"MinIO Connection Error: {e}")

    def save_file(self, file_stream, filename, content_type="image/jpeg"):
        """
        Загружает файл в MinIO.
        """
        if not self.client: raise Exception("MinIO client not initialized")
        try:
            # Сбрасываем указатель и определяем размер
            file_stream.seek(0, 2)
            file_size = file_stream.tell()
            file_stream.seek(0)

            # Загрузка
            self.client.put_object(
                self.bucket_name,
                filename,
                file_stream,
                length=file_size,
                content_type=content_type
            )
            return filename
        except Exception as e:
            print(f"Error saving to MinIO: {e}")
            raise e

    def delete_file(self, filename):
        """
        Удаляет файл из MinIO.
        """
        if not self.client: return
        try:
            self.client.remove_object(self.bucket_name, filename)
            print(f"File '{filename}' deleted from MinIO bucket '{self.bucket_name}'.")
        except Exception as e:
            print(f"Error deleting file from MinIO: {e}")
            raise e

    def send_local_file(self, filename, mimetype='image/jpeg'):
        """
        Скачивает файл из MinIO и отдает его клиенту через Flask.
        (Название метода сохранено для совместимости интерфейсов, 
         хотя файл берется из удаленного хранилища).
        """
        if not self.client: return jsonify({"error": "MinIO not available"}), 500
        
        response = None
        try:
            # Получаем поток данных от MinIO
            response = self.client.get_object(self.bucket_name, filename)
            
            # Читаем данные в память
            file_data = io.BytesIO(response.read())
            file_data.seek(0)
            
            return send_file(
                file_data, 
                mimetype=mimetype, 
                download_name=filename
            )
        except S3Error as e:
            print(f"MinIO Fetch Error: {e}")
            return jsonify({"error": "File not found in storage"}), 404
        except Exception as e:
            print(f"General Error fetching file: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            # Важно закрыть соединение с MinIO
            if response:
                response.close()
                response.release_conn()

    def get_local_file_path(self, filename):
        """
        Возвращает путь для внешнего доступа (если нужно).
        """
        return f"{self.endpoint}/{self.bucket_name}/{filename}"