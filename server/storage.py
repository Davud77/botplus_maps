import os
import io
from flask import send_file, jsonify
from minio import Minio
from minio.error import S3Error

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
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Создает бакет, если он не существует."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created.")
        except S3Error as e:
            print(f"MinIO Error (Ensure Bucket): {e}")

    def save_file(self, file_stream, filename, content_type="image/jpeg"):
        """
        Загружает файл в MinIO.
        """
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
            # Возвращаем путь (или просто имя файла, зависит от логики)
            return filename
        except Exception as e:
            print(f"Error saving to MinIO: {e}")
            raise e

    def delete_file(self, filename):
        """
        Удаляет файл из MinIO.
        Используется при откате транзакции (Rollback) или удалении записи.
        """
        try:
            self.client.remove_object(self.bucket_name, filename)
            print(f"File '{filename}' deleted from MinIO bucket '{self.bucket_name}'.")
        except Exception as e:
            print(f"Error deleting file from MinIO: {e}")
            # Мы логгируем ошибку, но обычно не прерываем выполнение, 
            # так как это чаще всего cleanup-операция.
            raise e

    def send_local_file(self, filename, mimetype='image/jpeg'):
        """
        Скачивает файл из MinIO и отдает его клиенту через Flask.
        """
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