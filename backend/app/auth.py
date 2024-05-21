from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import psycopg2
import psycopg2.extras
import json
import os

login_blueprint = Blueprint('login', __name__)

def load_db_config():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, '../db_config.json')
    with open(config_path, 'r') as file:
        return json.load(file)

db_config = load_db_config()

def connect_db():
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password']
    )

@login_blueprint.route('/login', methods=['POST'])
@cross_origin(supports_credentials=True)
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
