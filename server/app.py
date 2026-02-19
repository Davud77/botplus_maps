# server/app.py
from flask import Flask, request, make_response, send_from_directory, jsonify
from flask_cors import CORS
from flask_compress import Compress
from pathlib import Path
import os
import re
import config
import time
import random
from werkzeug.security import generate_password_hash

# --- Database / Repository Imports ---
try:
    from repositories import user_repository
except ImportError:
    print("Warning: Could not import user_repository. Database operations might fail.")
    user_repository = None

# --- Blueprint Imports ---
try:
    from controllers.auth_controller import auth_blueprint
except Exception as e:
    print(f"Warning: Could not import auth_blueprint. {e}")
    auth_blueprint = None

try:
    from controllers.pano_controller import pano_blueprint
except Exception as e:
    print(f"Warning: Could not import pano_blueprint. {e}")
    pano_blueprint = None

try:
    from controllers.ortho_controller import ortho_blueprint
except Exception as e:
    print(f"Warning: Could not import ortho_blueprint. {e}")
    ortho_blueprint = None

try:
    from controllers.vector import vector_bp
except Exception as e:
    print(f"Warning: Could not import vector_bp. {e}")
    vector_bp = None

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

def ensure_default_admin():
    """
    Checks if the default admin user exists in the database.
    If not, creates it using credentials from config/env.
    """
    if user_repository is None:
        return

    # Small random delay based on PID to desynchronize workers
    time.sleep((os.getpid() % 10) * 0.2 + random.uniform(0.1, 0.5))

    # Читаем креды администратора из .env (с фоллбэком)
    username = os.getenv("DEFAULT_ADMIN_USERNAME", getattr(config, "DEFAULT_ADMIN_USERNAME", "admin"))
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", getattr(config, "DEFAULT_ADMIN_PASSWORD", "change_me_please"))

    print(f"[Worker {os.getpid()}] Startup: Checking for default admin user '{username}'...")

    try:
        existing_user = user_repository.get_user_by_username(username)
        
        if existing_user:
            print(f"[Worker {os.getpid()}] Startup: User '{username}' already exists. Skipping creation.")
        else:
            print(f"[Worker {os.getpid()}] Startup: User '{username}' not found. Creating...")
            pw_hash = generate_password_hash(password)
            new_id = user_repository.create_user(username, pw_hash)
            
            if new_id:
                print(f"[Worker {os.getpid()}] Startup: User '{username}' successfully created (ID: {new_id}).")
            else:
                check_again = user_repository.get_user_by_username(username)
                if check_again:
                     print(f"[Worker {os.getpid()}] Startup: User '{username}' was created by another worker.")
                else:
                     print(f"[Worker {os.getpid()}] Startup: Failed to create user '{username}'. Check DB connection.")
                
    except Exception as e:
        print(f"[Worker {os.getpid()}] Startup Warning: Could not verify/create admin. Error: {e}")

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
        MAX_CONTENT_LENGTH= 4 * 1024 * 1024 * 1024,  # Upload limit 4 GB
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
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        
        # Disable caching for API, but keep for map tiles
        if 'application/vnd.mapbox-vector-tile' not in response.headers.get('Content-Type', ''):
             response.headers["Cache-Control"] = "no-store"
             
        return response

    @app.route("/<path:any_path>", methods=["OPTIONS"])
    def cors_preflight(any_path):
        return make_response("", 204)

    # ---------------- API REGISTRATION (Routing) ----------------
    if auth_blueprint:
        app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    
    if vector_bp:
        app.register_blueprint(vector_bp, url_prefix="/api")

    if pano_blueprint:
        app.register_blueprint(pano_blueprint, url_prefix="/api")
    
    if ortho_blueprint:
        app.register_blueprint(ortho_blueprint, url_prefix="/api")

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

    # --- INITIALIZATION CHECKS ---
    with app.app_context():
        # Only run admin ensure if not in a pure static context (optional, but safe)
        ensure_default_admin()

    return app

if __name__ == "__main__":
    application = create_app()
    # Read port from env, fallback to 5000
    port = int(os.getenv("APP_PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=(os.getenv("APP_ENV") == "development"))