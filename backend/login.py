from flask import Blueprint, request, jsonify
import psycopg2
import psycopg2.extras

# Создаем экземпляр Blueprint
login_blueprint = Blueprint('login', __name__)

def connect_db():
    conn = psycopg2.connect(
        host='192.168.1.79',
        port='5432',
        database='pb_user',
        user='postgres',
        password='password'
    )
    return conn

@login_blueprint.route('/login', methods=['POST'])
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
