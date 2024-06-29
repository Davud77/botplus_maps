from flask import Blueprint, request, jsonify
from PIL import Image
import piexif
import json
import os
from minio import Minio
import psycopg2
from datetime import datetime
import io

upload_blueprint = Blueprint('upload', __name__)

def load_db_config():
    dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    config_path = os.path.join(dir_path, 'db_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)

def load_minio_config():
    dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    config_path = os.path.join(dir_path, 'minio_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)

db_config = load_db_config()
minio_config = load_minio_config()

minio_client = Minio(
    minio_config['url'].split('//')[1],
    access_key=minio_config['accessKey'],
    secret_key=minio_config['secretKey'],
    secure=minio_config['url'].startswith('https')
)

def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )

def get_gps_coordinates(exif_data):
    latitude = longitude = None
    gps_ifd = exif_data.get('GPS', {})

    if piexif.GPSIFD.GPSLatitude in gps_ifd and piexif.GPSIFD.GPSLatitudeRef in gps_ifd:
        lat_ref = gps_ifd[piexif.GPSIFD.GPSLatitudeRef].decode()
        lat = gps_ifd[piexif.GPSIFD.GPSLatitude]
        latitude = convert_to_degrees(lat)
        if lat_ref != 'N':
            latitude = -latitude

    if piexif.GPSIFD.GPSLongitude in gps_ifd and piexif.GPSIFD.GPSLongitudeRef in gps_ifd:
        lon_ref = gps_ifd[piexif.GPSIFD.GPSLongitudeRef].decode()
        lon = gps_ifd[piexif.GPSIFD.GPSLongitude]
        longitude = convert_to_degrees(lon)
        if lon_ref != 'E':
            longitude = -longitude

    return latitude, longitude

def convert_to_degrees(value):
    d, m, s = value
    return d[0] / d[1] + m[0] / m[1] / 60 + s[0] / s[1] / 3600

@upload_blueprint.route('/upload', methods=['POST'])
def upload_files():
    uploaded_files = request.files.getlist("files")
    tags = request.form.get("tags", "")
    successful_uploads = []
    failed_uploads = []
    skipped_files = []

    for file in uploaded_files:
        try:
            file_path = f"pano/{file.filename}"
            file_content = file.read()
            file_stream = io.BytesIO(file_content)
            file_stream.seek(0)

            with Image.open(file_stream) as img:
                exif_data = img._getexif()
                if exif_data:
                    exif_dict = piexif.load(img.info['exif'])
                    gps_data = get_gps_coordinates(exif_dict) if 'GPS' in exif_dict else (None, None)
                else:
                    raise ValueError("Файл без EXIF")

                if gps_data[0] is None or gps_data[1] is None:
                    raise ValueError("Файл без GPS координат")

                minio_client.put_object("pano", file_path, file_stream, len(file_content))

            conn = connect_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO panolist (filename, tags, latitude, longitude, upload_date) VALUES (%s, %s, %s, %s, %s)",
                (file.filename, tags, gps_data[0], gps_data[1], datetime.now())
            )
            conn.commit()
            cur.close()
            conn.close()
            successful_uploads.append(file.filename)
        except Exception as e:
            error_message = f"Ошибка: {str(e)}"
            print(error_message)
            failed_uploads.append(file.filename)
            skipped_files.append(error_message)

    return jsonify({
        "message": "Отчет о загрузке файлов",
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "skipped_files": skipped_files
    }), 200
