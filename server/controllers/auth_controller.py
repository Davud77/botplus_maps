# controllers/auth_controller.py
from flask import Blueprint, request, jsonify, make_response
from werkzeug.security import check_password_hash
import time

from services.auth_service import create_access_token, decode_access_token
from repositories.user_repository import get_user_by_username
import config

auth_blueprint = Blueprint("auth", __name__)

COOKIE_NAME = "access_token"


def _set_token_cookie(resp, token: str):
    resp.set_cookie(
        COOKIE_NAME,
        value=token,
        max_age=config.ACCESS_TOKEN_EXPIRES,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        domain=(config.SESSION_COOKIE_DOMAIN or None),
        path="/",
    )
    return resp


def _clear_token_cookie(resp):
    resp.set_cookie(
        COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        domain=(config.SESSION_COOKIE_DOMAIN or None),
        path="/",
    )
    return resp


@auth_blueprint.post("/login")
def login():
    """
    Логин по username/password.
    Успех: ставим HttpOnly cookie access_token и возвращаем {status:"ok"}.
    Ошибка: 400/401 с {status:"error"/"fail", message}.
    """
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"status": "error", "message": "Укажите логин и пароль"}), 400

        user = get_user_by_username(username)
        if not user or not check_password_hash(user["password"], password):
            # одинаковый ответ для защиты от перебора
            return jsonify({"status": "fail", "message": "Неверные учетные данные"}), 401

        token = create_access_token(
            {"uid": user["id"], "u": user["username"]},
            expires_in=config.ACCESS_TOKEN_EXPIRES,
        )
        resp = make_response(jsonify({"status": "ok"}), 200)
        return _set_token_cookie(resp, token)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_blueprint.post("/logout")
def logout():
    """Выход: гасим cookie access_token."""
    resp = make_response(jsonify({"status": "ok"}), 200)
    return _clear_token_cookie(resp)


@auth_blueprint.get("/me")
def me():
    """
    Проверка сессии по HttpOnly cookie.
    Возвращает authenticated: true/false и информацию о пользователе при успехе.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify({"authenticated": False}), 200

    payload = decode_access_token(token)
    if not payload:
        return jsonify({"authenticated": False}), 200

    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": payload.get("uid"),
                "username": payload.get("u"),
                "exp": payload.get("exp"),
                "exp_unix": int(payload.get("exp", 0)),
                "exp_human": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.gmtime(payload.get("exp", 0))
                ),
            },
        }
    ), 200
