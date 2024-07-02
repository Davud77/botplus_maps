from flask import Blueprint, request, jsonify
from PIL import Image
import piexif
import json
import os
from minio import Minio
from datetime import datetime
import io
import subprocess

upload_ortho_blueprint = Blueprint('upload_ortho', __name__)

def load_minio_config():
    dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    config_path = os.path.join(dir_path, 'minio_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)

minio_config = load_minio_config()

minio_client = Minio(
    minio_config['url'].split('//')[1],
    access_key=minio_config['accessKey'],
    secret_key=minio_config['secretKey'],
    secure=minio_config['url'].startswith('https')
)

def convert_to_cog(input_path, output_path):
    try:
        subprocess.check_call([
            'gdal_translate', input_path, output_path,
            '-of', 'COG',
            '-co', 'TILED=YES',
            '-co', 'COMPRESS=LZW',
            '-co', 'RESAMPLING=BILINEAR'
        ])
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error converting to COG: {str(e)}")

@upload_ortho_blueprint.route('/upload_ortho', methods=['POST'])
def upload_ortho():
    uploaded_files = request.files.getlist("files")
    tags = request.form.get("tags", "")
    successful_uploads = []
    failed_uploads = []
    skipped_files = []

    for file in uploaded_files:
        try:
            original_filename = file.filename
            temp_filename = f"{os.path.splitext(original_filename)[0]}_temp.tif"
            file_path = f"/tmp/{temp_filename}"
            cog_filename = f"{os.path.splitext(original_filename)[0]}_cog.tif"
            cog_path = f"/tmp/{cog_filename}"

            # Сохранение временного файла на диск
            file.save(file_path)

            # Преобразование в Cloud Optimized GeoTIFF
            convert_to_cog(file_path, cog_path)

            # Загрузка COG файла в Minio
            with open(cog_path, 'rb') as cog_file:
                file_size = os.path.getsize(cog_path)
                minio_client.put_object("orthophoto", f"orthophoto/{cog_filename}", cog_file, file_size)

            # Удаление временных файлов
            os.remove(file_path)
            os.remove(cog_path)

            successful_uploads.append(original_filename)
        except Exception as e:
            error_message = f"Произошла ошибка при загрузке файла {original_filename}: {str(e)}"
            print(error_message)
            failed_uploads.append(original_filename)
            skipped_files.append(error_message)

    return jsonify({
        "message": "Отчет о загрузке файлов",
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "skipped_files": skipped_files
    }), 200
