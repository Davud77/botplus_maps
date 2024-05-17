from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import psycopg2
import psycopg2.extras
import json
import os

# Создаем экземпляр Blueprint
login_blueprint = Blueprint('login', __name__)

# Функция для загрузки конфигурации базы данных
def load_db_config():
    dir_path = os.path.dirname(os.path.realpath(__file__))  # Получение директории текущего файла
    config_path = os.path.join(dir_path, 'db_config.json')  # Формирование пути к файлу конфигурации
    with open(config_path, 'r') as file:  # Открытие файла конфигурации
        return json.load(file)  # Чтение и возврат данных конфигурации

db_config = load_db_config()  # Загрузка конфигурации базы данных

# Функция для подключения к базе данных
def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )

@login_blueprint.route('/login', methods=['POST'])
@cross_origin(supports_credentials=True)  # Разрешить CORS для этого маршрута и поддерживать учетные данные
def login():
    username = request.json['username']
    password = request.json['password']
    
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute('SELECT * FROM public.users WHERE username = %s AND password = %s', (username, password))
        user = cur.fetchone()
        if user:
            return jsonify({'status': 'success', 'message': 'Login successful'}), 200
        else:
            return jsonify({'status': 'fail', 'message': 'Invalid username or password'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(login_blueprint)
    app.run(debug=True, port=5000)
