# ./backend/controllers/auth_controller.py
from flask import Blueprint, request, jsonify, make_response
from werkzeug.security import check_password_hash
from flask_cors import cross_origin
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


@auth_blueprint.route("/login", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
def login():
    """
    Login by username/password.
    Success: sets HttpOnly access_token cookie and returns {status:"ok"}.
    Error: 400/401 with {status:"error"/"fail", message}.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"status": "error", "message": "Please provide username and password"}), 400

        user = get_user_by_username(username)
        if not user or not check_password_hash(user["password"], password):
            # Same response to protect against enumeration
            return jsonify({"status": "fail", "message": "Invalid credentials"}), 401

        token = create_access_token(
            {"uid": user["id"], "u": user["username"]},
            expires_in=config.ACCESS_TOKEN_EXPIRES,
        )
        resp = make_response(jsonify({"status": "ok"}), 200)
        return _set_token_cookie(resp, token)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_blueprint.route("/logout", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
def logout():
    """Logout: clears access_token cookie."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    resp = make_response(jsonify({"status": "ok"}), 200)
    return _clear_token_cookie(resp)


@auth_blueprint.route("/me", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def me():
    """
    Check session via HttpOnly cookie.
    Returns authenticated: true/false and user info on success.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

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