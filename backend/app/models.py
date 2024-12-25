from minio import Minio
from datetime import timedelta

minio_client = Minio(
    "localhost:9000",
    access_key="RtE-K_pchB_Wnu2scm3jFA",
    secret_key="EYt5QD6ygkgQvBPKJNW-JjotwZcI69OVJkUptzsAxHo",
    secure=False
)

# Попробуйте получить список бакетов (проверка соединения)
print(minio_client.list_buckets())

# Проверьте, есть ли бакет 'pano'
found = minio_client.bucket_exists("pano")
print("Bucket 'pano' exists?", found)

# Попробуйте вручную сгенерировать ссылку
url = minio_client.presigned_get_object(
    "pano",
    "GSAB5464_20221023.JPG",  # или "pano/GSAB5464_20221023.JPG", если так хранится
    expires=timedelta(hours=12)
)
print(url)
