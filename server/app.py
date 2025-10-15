from flask import Flask, request, make_response, send_from_directory, jsonify
from flask_cors import CORS
from pathlib import Path
import os
import re
import config

# Пытаемся подключить блюпринты (если каких-то нет — приложение всё равно стартует)
try:
    from controllers.auth_controller import auth_blueprint
except Exception:
    auth_blueprint = None
try:
    from controllers.pano_controller import pano_blueprint
except Exception:
    pano_blueprint = None
try:
    from controllers.ortho_controller import ortho_blueprint
except Exception:
    ortho_blueprint = None

# Пути к статике (сохраняем совместимость с текущей структурой)
# Прежний код поднимался на один уровень вверх: parents[1] → /app
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR   = getattr(config, "PUBLIC_DIR", PROJECT_ROOT / "public")
BUILD_DIR    = PUBLIC_DIR / "build"

# Разрешённые источники CORS: из config.CLIENT_ORIGINS + опционально поддомены *.botplus.ru
ALLOWED_ORIGINS = list(getattr(config, "CLIENT_ORIGINS", [])) + [re.compile(r"^https://.*\.botplus\.ru$")]

def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    for o in ALLOWED_ORIGINS:
        if isinstance(o, re.Pattern):
            if o.match(origin):
                return True
        else:
            if origin == o:
                return True
    return False

def create_app():
    # Явно отключаем дефолтную статику Flask, чтобы сами контролировать раздачу SPA
    app = Flask(__name__, static_folder=None)
    app.secret_key = config.SECRET_KEY

    # Куки/сессии и общие лимиты
    app.config.update(
        SESSION_COOKIE_DOMAIN=(config.SESSION_COOKIE_DOMAIN or None),
        SESSION_COOKIE_SAMESITE=getattr(config, "COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=getattr(config, "COOKIE_SECURE", False),
        SESSION_COOKIE_HTTPONLY=True,
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024,  # 1 ГБ
    )

    # CORS: достаточно описать /api/* — статика и SPA ходят с того же origin
    CORS(
        app,
        resources={r"/api/*": {"origins": ALLOWED_ORIGINS}},
        supports_credentials=True,
        expose_headers=["Content-Type", "Authorization"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin_allowed(origin):
            # если запрос пришёл с допустимого источника — отзеркалим его
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Cache-Control"] = "no-store"
        return response

    # Универсальный preflight для нестандартных путей
    @app.route("/<path:any_path>", methods=["OPTIONS"])
    def cors_preflight(any_path):
        return make_response("", 204)

    # ---------------- API ----------------
    # Авторизация — строго под /api/auth/*
    if auth_blueprint:
        app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    # Остальные блюпринты регистрируем как есть (их внутренние пути уже могут начинаться с /api/*)
    if pano_blueprint:
        app.register_blueprint(pano_blueprint)
    if ortho_blueprint:
        app.register_blueprint(ortho_blueprint)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    # ---------------- Статика / SPA ----------------
    # favicon/manifest: сперва из build/, если нет — из public/
    @app.route("/favicon.ico")
    def favicon():
        if (BUILD_DIR / "favicon.ico").exists():
            return send_from_directory(BUILD_DIR, "favicon.ico", conditional=True)
        return send_from_directory(PUBLIC_DIR, "favicon.ico", conditional=True)

    @app.route("/manifest.json")
    def manifest():
        if (BUILD_DIR / "manifest.json").exists():
            return send_from_directory(BUILD_DIR, "manifest.json", conditional=True)
        return send_from_directory(PUBLIC_DIR, "manifest.json", conditional=True)

    # /static/* → build/static/* (CRA/SPA артефакты)
    @app.route("/static/<path:filename>")
    def static_from_build(filename):
        build_static = BUILD_DIR / "static"
        public_static = PUBLIC_DIR / "static"
        if (build_static / filename).exists():
            return send_from_directory(build_static, filename, conditional=True)
        # fallback на /public/static (на случай dev-артефактов)
        if (public_static / filename).exists():
            return send_from_directory(public_static, filename, conditional=True)
        return ("Not Found", 404)

    # /assets/* — на будущее (vite-паттерн)
    @app.route("/assets/<path:filename>")
    def assets_from_build(filename):
        build_assets = BUILD_DIR / "assets"
        public_assets = PUBLIC_DIR / "assets"
        if (build_assets / filename).exists():
            return send_from_directory(build_assets, filename, conditional=True)
        if (public_assets / filename).exists():
            return send_from_directory(public_assets, filename, conditional=True)
        return ("Not Found", 404)

    # Любые не-API пути → SPA index.html
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_fallback(path: str):
        candidate = BUILD_DIR / path
        if candidate.is_file():
            rel = os.path.relpath(candidate, BUILD_DIR)
            return send_from_directory(BUILD_DIR, rel, conditional=True)

        index_file = (BUILD_DIR / "index.html") if (BUILD_DIR / "index.html").exists() else (PUBLIC_DIR / "index.html")
        if not index_file.exists():
            return {
                "ok": False,
                "error": "index.html not found",
                "looked_in": [str(BUILD_DIR / "index.html"), str(PUBLIC_DIR / "index.html")],
            }, 500
        return send_from_directory(index_file.parent, index_file.name, conditional=True)

    return app

if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=False)
