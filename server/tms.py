import os
import subprocess
import boto3
from botocore.client import Config

# Параметры доступа к MinIO
endpoint_url = 'http://192.168.1.79:9081'
access_key = 'PEx7ziPck6GNQyCX8Bfn'
secret_key = '50M47bzpabapjR7VK1LdEakWHSoATg9GYXZ0xLlm'
api_version = 's3v4'

# Создание клиента S3
s3_client = boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(signature_version=api_version),
    region_name='us-east-1'
)

def download_tif(bucket_name, object_name, local_file_name):
    s3_client.download_file(bucket_name, object_name, local_file_name)

def upload_directory(directory_path, bucket_name):
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, directory_path)
            s3_path = os.path.join(relative_path)
            s3_client.upload_file(local_path, bucket_name, s3_path)

def process_tif_to_tiles(input_tif, output_dir):
    subprocess.run(['gdal2tiles.py', '-p', 'raster', input_tif, output_dir], check=True)

# Имя файла и пути
input_tif = 'input.tif'
output_dir = 'tiles_output'

# Загрузка .tif файла из bucket 'sources'
download_tif('sources', input_tif, input_tif)

# Обработка файла в тайлы
process_tif_to_tiles(input_tif, output_dir)

# Загрузка сгенерированных тайлов в bucket 'tms'
upload_directory(output_dir, 'tms')

# Удаление локальных файлов после загрузки
os.remove(input_tif)
shutil.rmtree(output_dir)
