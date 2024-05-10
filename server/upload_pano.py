from flask import Flask, request, jsonify
from PIL import Image
import piexif
import json
import os
from minio import Minio
import psycopg2

app = Flask(__name__)

# Загрузка конфигурации базы данных
def load_db_config():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, 'db_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)  # Возвращает конфигурацию в виде словаря

# Загрузка конфигурации MinIO
def load_minio_config():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, 'minio_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)  # Возвращает конфигурацию MinIO в виде словаря

db_config = load_db_config()
minio_config = load_minio_config()

# Создание подключения к базе данных
def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )

# Извлечение GPS координат из EXIF данных
def get_gps_coordinates(exif_data):
    latitude = longitude = None
    if piexif.GPSIFD.GPSLatitudeRef and piexif.GPSIFD.GPSLatitude in exif_data:
        lat_ref = exif_data[piexif.GPSIFD.GPSLatitudeRef].decode()
        lat = exif_data[piexif.GPSIFD.GPSLatitude]
        latitude = convert_to_degrees(lat)
        if lat_ref != 'N':  # Инвертируем значение, если не северное полушарие
            latitude = -latitude

    if piexif.GPSIFD.GPSLongitudeRef and piexif.GPSIFD.GPSLongitude in exif_data:
        lon_ref = exif_data[piexif.GPSIFD.GPSLongitudeRef].decode()
        lon = exif_data[piexif.GPSIFD.GPSLongitude]
        longitude = convert_to_degrees(lon)
        if lon_ref != 'E':  # Инвертируем значение, если не восточное полушарие
            longitude = -longitude

    return latitude, longitude

# Конвертация координат в градусы
def convert_to_degrees(value):
    d, m, s = value
    return d[0] / d[1] + m[0] / m[1] / 60 + s[0] / s[1] / 3600

# Маршрут Flask для загрузки файлов
@app.route('/upload', methods=['POST'])
def upload_files():
    uploaded_files = request.files.getlist("files")  # Получение списка файлов
    tags = request.form.get("tags", "")
    successful_uploads = []
    failed_uploads = []

    for file in uploaded_files:
        try:
            file_path = f"pano/{file.filename}"  # Формирование пути для сохранения файла в MinIO
            minio_client.put_object("pano", file_path, file, file.content_length)  # Загрузка файла в MinIO

            with Image.open(file.stream) as img:
                exif_data = img._getexif()  # Извлечение EXIF данных
                if exif_data:
                    exif_dict = piexif.load(img.info['exif'])
                    gps_data = get_gps_coordinates(exif_dict['GPS']) if 'GPS' in exif_dict else (None, None)

            conn = connect_db()  # Подключение к базе данных
            cur = conn.cursor()
            cur.execute("INSERT INTO uploads (filename, tags, latitude, longitude) VALUES (%s, %s, %s, %s)",
                        (file.filename, tags, gps_data[0], gps_data[1]))
            conn.commit()  # Фиксация изменений в базе
            cur.close()
            conn.close()
            successful_uploads.append(file.filename)
        except Exception as e:
            print(f"Не удалось загрузить файл {file.filename}: {str(e)}")
            failed_uploads.append(file.filename)

    return jsonify({
        "message": "Отчет о загрузке файлов",
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads
    }), 200

# Запуск приложения
if __name__ == '__main__':
    app.run(debug=True)
