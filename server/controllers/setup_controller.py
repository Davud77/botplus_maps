"""One-time administrator enrollment, serialized across processes by PostgreSQL."""
import re
from flask import Blueprint, jsonify, request, make_response
from werkzeug.security import generate_password_hash
from database import Database
from controllers.auth_controller import _set_token_cookie
from services.auth_service import create_access_token
import config

setup_blueprint = Blueprint("setup", __name__)
SETUP_LOCK = 941027002


def setup_required():
    # Existing installations are never reopened, including legacy accounts.
    with Database().cursor() as cursor:
        cursor.execute("SELECT (EXISTS (SELECT 1 FROM users) OR EXISTS (SELECT 1 FROM app_installation)) AS initialized")
        return not cursor.fetchone()["initialized"]


@setup_blueprint.get("/status")
def status():
    try:
        return jsonify(setup_required=setup_required())
    except Exception:
        return jsonify(message="База данных недоступна. Проверьте подключение и повторите попытку."), 503


@setup_blueprint.post("/initialize")
def initialize():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(message="Ожидаются логин и пароль."), 400
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{3,50}", username):
        return jsonify(message="Логин: от 3 до 50 латинских букв, цифр, точек, дефисов или подчёркиваний."), 400
    if not isinstance(password, str) or not 12 <= len(password) <= 128 or not password.strip():
        return jsonify(message="Пароль должен содержать от 12 до 128 символов."), 400
    try:
        if not setup_required():
            return jsonify(message="Настройка уже завершена. Войдите в существующий аккаунт."), 409
        password_hash = generate_password_hash(password)
        with Database().cursor(write=True) as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (SETUP_LOCK,))
            cursor.execute("SELECT (EXISTS (SELECT 1 FROM users) OR EXISTS (SELECT 1 FROM app_installation)) AS initialized")
            if cursor.fetchone()["initialized"]:
                return jsonify(message="Настройка уже завершена. Войдите в существующий аккаунт."), 409
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin') RETURNING id",
                           (username, password_hash))
            uid = cursor.fetchone()["id"]
            cursor.execute("INSERT INTO app_installation (id,rbac_migrated) VALUES (1,TRUE)")
        token = create_access_token({"uid": uid, "u": username}, expires_in=config.ACCESS_TOKEN_EXPIRES)
        return _set_token_cookie(make_response(jsonify(status="ok"), 201), token)
    except Exception:
        return jsonify(message="Не удалось завершить настройку. Проверьте подключение к базе данных."), 503
