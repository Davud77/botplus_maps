from flask import Flask, jsonify
from flask_cors import CORS
import psycopg2
import json
import os
from minio import Minio
from datetime import timedelta

app = Flask(__name__)
CORS(app)  # Включение CORS для доступа к API с любого домена

# Функция для загрузки конфигурационного файла
def load_config(filename):
    dir_path = os.path.dirname(os.path.realpath(__file__))  # Получение директории исполняемого файла
    config_path = os.path.join(dir_path, filename)  # Формирование пути к файлу конфигурации
    with open(config_path, 'r') as file:  # Открытие файла конфигурации
        return json.load(file)  # Чтение JSON-конфигурации

# Загрузка конфигураций для базы данных и Minio
db_config = load_config('db_config.json')
minio_config = load_config('minio_config.json')

# Инициализация клиента Minio с конфигурационными данными
minio_client = Minio(
    minio_config['url'].split('//')[1],
    access_key=minio_config['accessKey'],
    secret_key=minio_config['secretKey'],
    secure=minio_config['url'].startswith('https')
)

# Функция для подключения к базе данных PostgreSQL
def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )



# Создание временного URL для доступа к объектам в Minio
def create_presigned_url(bucket, object_name):
    try:
        return minio_client.presigned_get_object(bucket, object_name, expires=timedelta(hours=12))
    except Exception as e:
        print("Ошибка при создании подписанного URL:", e)
        return None

# Маршрут API для получения списка панорам
@app.route('/panoramas', methods=['GET'])
def get_panoramas():
    conn = connect_db()  # Подключение к базе данных
    cursor = conn.cursor()  # Создание курсора для выполнения запросов
    try:
        cursor.execute("SELECT filename, latitude, longitude, tags FROM panolist")  # Выполнение SQL-запроса
        records = cursor.fetchall()  # Получение всех записей из результата запроса
        panoramas = [
            {
                'filename': create_presigned_url('pano', 'pano/' + row[0]),  # Создание URL для каждого файла
                'latitude': row[1],
                'longitude': row[2],
                'tags': row[3]
            }
            for row in records
        ]
        return jsonify(panoramas)  # Возврат данных в формате JSON
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Возвращение ошибки, если операция не удалась
    finally:
        cursor.close()  # Закрытие курсора
        conn.close()  # Закрытие соединения с базой данных




        

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Запуск приложения на порту 5000 с включенным режимом отладки