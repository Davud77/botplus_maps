"""Account security and administrator-only user management."""
import re
from flask import Blueprint, request, jsonify, g
from psycopg2.errors import UniqueViolation
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database
from services.permissions import require_admin, ROLES
from controllers.auth_controller import _set_token_cookie
from services.auth_service import create_access_token
import config

account_blueprint = Blueprint('accounts', __name__)
USER_FIELDS = 'id, username, role, is_active, created_at'
ADMIN_LOCK = 941027003


def valid_password(password):
    return isinstance(password, str) and 12 <= len(password) <= 128 and bool(password.strip())


@account_blueprint.post('/account/password')
def change_password():
    request.max_content_length = 4096
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not valid_password(data.get('new_password')) or not isinstance(data.get('current_password'), str):
        return jsonify(message='Укажите текущий пароль и новый пароль длиной 12–128 символов.'), 400
    if data['current_password'] == data['new_password']:
        return jsonify(message='Новый пароль должен отличаться от текущего.'), 400
    password_hash = generate_password_hash(data['new_password'])
    with Database().cursor(write=True) as cursor:
        cursor.execute('SELECT password, session_version FROM users WHERE id=%s FOR UPDATE', (g.current_user_id,))
        user = cursor.fetchone()
        if not user or not check_password_hash(user['password'], data['current_password']):
            return jsonify(message='Текущий пароль указан неверно.'), 400
        cursor.execute('UPDATE users SET password=%s, session_version=session_version+1 WHERE id=%s RETURNING session_version',
                       (password_hash, g.current_user_id))
        version = cursor.fetchone()['session_version']
    token = create_access_token({'uid': g.current_user_id, 'u': g.current_user['username'], 'ver': version}, expires_in=config.ACCESS_TOKEN_EXPIRES)
    return _set_token_cookie(jsonify(status='ok', message='Пароль изменён. Остальные сеансы завершены.'), token)


@account_blueprint.get('/users')
def list_users():
    require_admin()
    with Database().cursor() as cursor:
        cursor.execute(f'SELECT {USER_FIELDS} FROM users ORDER BY id LIMIT 1000')
        users = cursor.fetchall()
    return jsonify(users=users)


@account_blueprint.post('/users')
def create_user():
    require_admin()
    request.max_content_length = 4096
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message='Неверный формат запроса.'), 400
    username, password, role = data.get('username'), data.get('password'), data.get('role')
    if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,50}', username) or not valid_password(password) or not isinstance(role, str) or role not in ROLES:
        return jsonify(message='Проверьте логин, пароль (12–128 символов) и роль.'), 400
    password_hash = generate_password_hash(password)
    try:
        with Database().cursor(write=True) as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADMIN_LOCK,))
            cursor.execute('SELECT role,is_active FROM users WHERE id=%s', (g.current_user_id,))
            actor = cursor.fetchone()
            if not actor or not actor['is_active'] or actor['role'] != 'admin':
                return jsonify(message='Полномочия администратора изменились.'), 403
            cursor.execute(f'INSERT INTO users (username,password,role) VALUES (%s,%s,%s) RETURNING {USER_FIELDS}', (username, password_hash, role))
            user = cursor.fetchone()
        return jsonify(user=user), 201
    except UniqueViolation:
        return jsonify(message='Такой логин уже занят.'), 409


@account_blueprint.patch('/users/<int:user_id>')
def update_user(user_id):
    require_admin()
    request.max_content_length = 4096
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - {'role', 'is_active'} or not data:
        return jsonify(message='Укажите роль или состояние аккаунта.'), 400
    if ('role' in data and (not isinstance(data['role'], str) or data['role'] not in ROLES)) or ('is_active' in data and type(data['is_active']) is not bool):
        return jsonify(message='Недопустимая роль или состояние.'), 400
    with Database().cursor(write=True) as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADMIN_LOCK,))
        # Recheck after the lock: two administrators cannot demote one another concurrently.
        cursor.execute('SELECT role,is_active FROM users WHERE id=%s', (g.current_user_id,))
        actor = cursor.fetchone()
        if not actor or not actor['is_active'] or actor['role'] != 'admin':
            return jsonify(message='Полномочия администратора изменились.'), 403
        cursor.execute('SELECT role,is_active FROM users WHERE id=%s FOR UPDATE', (user_id,))
        target = cursor.fetchone()
        if not target:
            return jsonify(message='Пользователь не найден.'), 404
        role, active = data.get('role', target['role']), data.get('is_active', target['is_active'])
        if target['role'] == 'admin' and target['is_active'] and (role != 'admin' or not active):
            cursor.execute("SELECT count(*) AS count FROM users WHERE role='admin' AND is_active")
            if cursor.fetchone()['count'] <= 1:
                return jsonify(message='Нельзя отключить или понизить последнего администратора.'), 409
        cursor.execute(f'UPDATE users SET role=%s,session_version=session_version+CASE WHEN is_active AND NOT %s THEN 1 ELSE 0 END,is_active=%s WHERE id=%s RETURNING {USER_FIELDS}', (role, active, active, user_id))
        user = cursor.fetchone()
    return jsonify(user=user)
