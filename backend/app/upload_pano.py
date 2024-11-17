from flask import Blueprint, request, jsonify
from PIL import Image
import piexif
import os
from minio import Minio
import psycopg2
from datetime import datetime
import io

upload_blueprint = Blueprint('upload', __name__)

def connect_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'botplus'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'password')
    )

minio_client = Minio(
    os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
    access_key=os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
    secret_key=os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
    secure=os.environ.get('MINIO_SECURE', 'False').lower() == 'true'
)

def get_gps_coordinates(exif_data):
    latitude = longitude = altitude = None
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

    if piexif.GPSIFD.GPSAltitude in gps_ifd:
        altitude = gps_ifd[piexif.GPSIFD.GPSAltitude]
        altitude = altitude[0] / altitude[1] if isinstance(altitude, tuple) else altitude

    return latitude, longitude, altitude

def convert_to_degrees(value):
    d, m, s = value
    return d[0] / d[1] + m[0] / m[1] / 60 + s[0] / s[1] / 3600

def sanitize_string(value):
    """ Remove NUL characters from strings """
    if isinstance(value, bytes):
        value = value.decode('utf-8', 'ignore')
    return value.replace('\x00', '')

@upload_blueprint.route('/upload', methods=['POST'])
def upload_files():
    uploaded_files = request.files.getlist("files")
    tags = request.form.get("tags", "")
    user_id = request.form.get("user_id", 1)  # Получаем user_id из формы, если есть
    successful_uploads = []
    failed_uploads = []
    skipped_files = []

    conn = connect_db()
    cur = conn.cursor()

    for file in uploaded_files:
        original_filename = file.filename
        try:
            file_content = file.read()
            file_stream = io.BytesIO(file_content)
            file_stream.seek(0)

            with Image.open(file_stream) as img:
                exif_data = img._getexif()
                if exif_data:
                    exif_dict = piexif.load(img.info['exif'])
                    gps_data = get_gps_coordinates(exif_dict) if 'GPS' in exif_dict else (None, None, None)
                else:
                    raise ValueError("Файл без EXIF")

                if gps_data[0] is None or gps_data[1] is None:
                    raise ValueError("Файл без GPS координат")

                # Extract additional EXIF fields
                file_size = len(file_content)
                file_type = file.mimetype
                full_pano_width_pixels = img.width
                full_pano_height_pixels = img.height
                first_photo_date = exif_dict.get('Exif', {}).get(piexif.ExifIFD.DateTimeOriginal, None)
                if first_photo_date:
                    first_photo_date = datetime.strptime(sanitize_string(first_photo_date), '%Y:%m:%d %H:%M:%S')
                    date_str = first_photo_date.strftime('%Y%m%d')
                    new_filename = f"{os.path.splitext(file.filename)[0]}_{date_str}.JPG"
                else:
                    new_filename = file.filename

                model = exif_dict.get('0th', {}).get(piexif.ImageIFD.Model, None)
                if model:
                    model = sanitize_string(model)
                focal_length = exif_dict.get('Exif', {}).get(piexif.ExifIFD.FocalLength, None)
                if focal_length:
                    focal_length = focal_length[0] / focal_length[1] if isinstance(focal_length, tuple) else focal_length

                # Upload the file to Minio with the new filename
                file_stream.seek(0)
                minio_client.put_object("pano", new_filename, file_stream, len(file_content))

                # Prepare the geom value
                geom = f"POINT Z({gps_data[1]} {gps_data[0]} {gps_data[2] if gps_data[2] else 0})"

            cur.execute(
                """
                INSERT INTO panolist (
                    filename, tags, latitude, longitude, upload_date, user_id, file_size, file_type, 
                    full_pano_width_pixels, full_pano_height_pixels, first_photo_date, model, altitude, focal_length, geom
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                """,
                (
                    new_filename, tags, gps_data[0], gps_data[1], datetime.now(), user_id, file_size, file_type,
                    full_pano_width_pixels, full_pano_height_pixels, first_photo_date, model, gps_data[2], focal_length, geom
                )
            )
            conn.commit()
            successful_uploads.append(original_filename)
        except Exception as e:
            error_message = f"Ошибка: {str(e)}"
            print(error_message)
            failed_uploads.append(original_filename)
            skipped_files.append(error_message)

    cur.close()
    conn.close()

    return jsonify({
        "message": "Отчет о загрузке файлов",
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "skipped_files": skipped_files
    }), 200