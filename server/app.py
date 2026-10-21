# server/app.py
from flask import Flask, request, make_response, send_from_directory, jsonify
from flask_cors import CORS
from flask_compress import Compress
from pathlib import Path
import os
import re
import config

# Required routes fail at startup instead of disappearing behind a healthy response.
from controllers.auth_controller import auth_blueprint
from controllers.setup_controller import setup_blueprint
from controllers.pano_controller import create_pano_blueprint
from controllers.ortho_controller import create_ortho_blueprint
from controllers.vector import vector_bp

# Paths to static files (Frontend build)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR   = getattr(config, "PUBLIC_DIR", PROJECT_ROOT / "public")
BUILD_DIR    = PUBLIC_DIR / "build"

# --- Парсинг CORS из .env ---
raw_origins = os.getenv("CLIENT_ORIGINS", getattr(config, "CLIENT_ORIGINS", ""))
if isinstance(raw_origins, str):
    # Разбиваем строку по запятым и убираем пробелы
    client_origins_list = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    client_origins_list = list(raw_origins)

# Allowed CORS origins
ALLOWED_ORIGINS = client_origins_list + [re.compile(r"^https://.*\.botplus\.ru$")]

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
    app = Flask(__name__, static_folder=None)

    # Читаем секретные ключи из .env
    app.secret_key = os.getenv("SECRET_KEY", getattr(config, "SECRET_KEY", "fallback-secret-key"))

    # --- Безопасный парсинг настроек Cookie из .env ---
    cookie_secure_env = os.getenv("COOKIE_SECURE", getattr(config, "COOKIE_SECURE", "False"))
    is_cookie_secure = str(cookie_secure_env).lower() in ("true", "1", "yes", "t")

    cookie_domain = os.getenv("SESSION_COOKIE_DOMAIN", getattr(config, "SESSION_COOKIE_DOMAIN", ""))
    if not cookie_domain:  # Если пустая строка в .env, превращаем в None
        cookie_domain = None

    cookie_samesite = os.getenv("COOKIE_SAMESITE", getattr(config, "COOKIE_SAMESITE", "Lax"))

    # Cookie and limit settings
    app.config.update(
        SESSION_COOKIE_DOMAIN=cookie_domain,
        SESSION_COOKIE_SAMESITE=cookie_samesite,
        SESSION_COOKIE_SECURE=is_cookie_secure,
        SESSION_COOKIE_HTTPONLY=True,
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH= 1024 * 1024 * 1024 * 1024,
    )

    # ---------------- COMPRESSION SETTINGS (GZIP) ----------------
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html',
        'text/css',
        'text/xml',
        'application/json',
        'application/javascript',
        'application/vnd.mapbox-vector-tile'
    ]
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIN_SIZE'] = 500

    Compress(app)

    from http_policies import register_http_policies
    from services.auth_service import decode_access_token
    register_http_policies(app, decode_access_token, origin_allowed)

    # ---------------- CORS ----------------
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
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.vary.add("Origin")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"

        return response

    @app.route("/<path:any_path>", methods=["OPTIONS"])
    def cors_preflight(any_path):
        return make_response("", 204)

    # ---------------- API REGISTRATION (Routing) ----------------
    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    app.register_blueprint(setup_blueprint, url_prefix="/api/setup")
    app.register_blueprint(vector_bp, url_prefix="/api")
    app.register_blueprint(create_pano_blueprint(), url_prefix="/api")
    app.register_blueprint(create_ortho_blueprint(), url_prefix="/api")

    # API Health Check
    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "db": "postgres", "env": os.getenv("APP_ENV", "unknown")})

    # ---------------- STATIC SERVING (Frontend / SPA) ----------------

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

    @app.route("/static/<path:filename>")
    def static_from_build(filename):
        build_static = BUILD_DIR / "static"
        public_static = PUBLIC_DIR / "static"
        if (build_static / filename).exists():
            return send_from_directory(build_static, filename, conditional=True)
        if (public_static / filename).exists():
            return send_from_directory(public_static, filename, conditional=True)
        return ("Not Found", 404)

    @app.route("/assets/<path:filename>")
    def assets_from_build(filename):
        build_assets = BUILD_DIR / "assets"
        public_assets = PUBLIC_DIR / "assets"
        if (build_assets / filename).exists():
            return send_from_directory(build_assets, filename, conditional=True)
        if (public_assets / filename).exists():
            return send_from_directory(public_assets, filename, conditional=True)
        return ("Not Found", 404)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_fallback(path: str):
        if path == "api" or path.startswith("api/"):
            return jsonify({"error": "API endpoint not found"}), 404
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
    # Read port from env, fallback to 5000
    port = int(os.getenv("APP_PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=(os.getenv("APP_ENV") == "development"))
