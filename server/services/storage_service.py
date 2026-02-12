import json
import os
from storage import LocalStorage, MinioStorage
import config

class StorageService:
    def __init__(self):
        self.local = LocalStorage(config.ORTHO_FOLDER)
        self.minio = MinioStorage()
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Проверка и создание бакета при инициализации"""
        if self.minio.client:
            try:
                bucket_name = "orthophotos"
                if not self.minio.client.bucket_exists(bucket_name):
                    self.minio.client.make_bucket(bucket_name)
                    print(f"Bucket '{bucket_name}' created successfully.")
                
                # Устанавливаем политику Public Read
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                self.minio.client.set_bucket_policy(bucket_name, json.dumps(policy))
            except Exception as e:
                print(f"MinIO init warning: {e}")

    def upload_file(self, filename, filepath, content_type="image/tiff"):
        """Загрузка в MinIO"""
        if self.minio.client:
            self.minio.client.fput_object(
                "orthophotos", 
                filename, 
                filepath, 
                content_type=content_type
            )
            return True
        return False

    def download_file(self, filename, local_path):
        """Скачивание из MinIO в локальный путь"""
        if self.minio.client:
            self.minio.client.fget_object("orthophotos", filename, local_path)
            return True
        return False

    def delete_file(self, filename):
        """Удаление файла"""
        if self.minio.client:
            try:
                self.minio.delete_file(filename) # Используем метод обертки, если он там есть, или client.remove_object
                # Примечание: в твоем коде был self.minio.delete_file, предполагаю он реализован в MinioStorage
            except Exception as e:
                print(f"MinIO delete warning: {e}")

    def send_file(self, filename, mimetype="image/tiff"):
        """Отправка файла клиенту (Flask response)"""
        # Сначала пробуем MinIO
        if self.minio.client:
            try:
                # В твоем коде использовался send_local_file внутри MinioStorage? 
                # Если да, оставляем как было, переключая бакет
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = "orthophotos"
                response = self.minio.send_local_file(filename, mimetype=mimetype)
                self.minio.bucket_name = orig_bucket
                return response
            except Exception as e:
                print(f"MinIO download failed: {e}")
        
        # Фоллбек на локальное
        return self.local.send_local_file(filename, mimetype=mimetype)