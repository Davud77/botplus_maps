from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import psycopg2
import psycopg2.extras
import os

login_blueprint = Blueprint('login', __name__)

def connect_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'botplus'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'password')
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