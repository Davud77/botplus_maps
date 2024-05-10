from minio import Minio

minio_client = Minio(
    "192.168.1.79:9080",  # Убедитесь, что этот адрес правильный и без лишних путей
    access_key="PEx7ziPck6GNQyCX8Bfn",
    secret_key="50M47bzpabapjR7VK1LdEakWHSoATg9GYXZ0xLlm",
    secure=False  # Установите на True, если используется HTTPS
)

try:
    buckets = minio_client.list_buckets()
    print("Available buckets:")
    for bucket in buckets:
        print(bucket.name)
except Exception as e:
    print(f"Failed to connect to MinIO: {str(e)}")
