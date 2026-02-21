# server/services/storage_service.py
import json
import os
from storage import LocalStorage, MinioStorage
import config

class StorageService:
    def __init__(self):
        self.local = LocalStorage(config.ORTHO_FOLDER)
        self.minio = MinioStorage()
        # [NEW] Подтягиваем имя бакета из конфигурации (.env)
        self.bucket_name = getattr(config, 'MINIO_ORTHO_BUCKET', 'orthophotos')
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Проверка и создание бакета при инициализации"""
        if self.minio.client:
            try:
                # Используем динамическое имя бакета
                if not self.minio.client.bucket_exists(self.bucket_name):
                    self.minio.client.make_bucket(self.bucket_name)
                    print(f"Bucket '{self.bucket_name}' created successfully.")
                
                # Устанавливаем политику Public Read
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                        }
                    ]
                }
                self.minio.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            except Exception as e:
                print(f"MinIO init warning: {e}")

    def upload_file(self, filename, filepath, content_type="image/tiff"):
        """Загрузка в MinIO"""
        if self.minio.client:
            self.minio.client.fput_object(
                self.bucket_name, # [UPDATED]
                filename, 
                filepath, 
                content_type=content_type
            )
            return True
        return False

    def download_file(self, filename, local_path):
        """Скачивание из MinIO в локальный путь"""
        if self.minio.client:
            self.minio.client.fget_object(self.bucket_name, filename, local_path) # [UPDATED]
            return True
        return False

    def delete_file(self, filename):
        """Удаление файла"""
        if self.minio.client:
            try:
                # [UPDATED] Переключаем бакет перед удалением (как в send_file), 
                # чтобы случайно не удалить файл из бакета панорам
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = self.bucket_name
                
                self.minio.delete_file(filename) 
                
                self.minio.bucket_name = orig_bucket
            except Exception as e:
                print(f"MinIO delete warning: {e}")

    def send_file(self, filename, mimetype="image/tiff"):
        """Отправка файла клиенту (Flask response)"""
        # Сначала пробуем MinIO
        if self.minio.client:
            try:
                # Временно переключаем бакет базового класса на бакет ортофотопланов
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = self.bucket_name # [UPDATED]
                
                response = self.minio.send_local_file(filename, mimetype=mimetype)
                
                self.minio.bucket_name = orig_bucket
                return response
            except Exception as e:
                print(f"MinIO download failed: {e}")
        
        # Фоллбек на локальное
        return self.local.send_local_file(filename, mimetype=mimetype)