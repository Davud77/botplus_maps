# server/app.py
from flask import Flask, request, make_response, send_from_directory, jsonify
from flask_cors import CORS
from flask_compress import Compress
from pathlib import Path
import os
import re
import config

# Try to import blueprints. 
# If a part (e.g. Auth or Vector) is not configured, the server will still start.
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

# New controller for Vector (PostGIS)
try:
    from controllers.vector import vector_bp
except Exception as e:
    print(f"Warning: Could not import vector_bp. {e}")
    vector_bp = None

# Paths to static files (Frontend build)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR   = getattr(config, "PUBLIC_DIR", PROJECT_ROOT / "public")
BUILD_DIR    = PUBLIC_DIR / "build"

# Allowed CORS origins
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
    # Disable default Flask static handling, we will serve it manually for SPA
    app = Flask(__name__, static_folder=None)
    app.secret_key = config.SECRET_KEY

    # Cookie and limit settings
    app.config.update(
        SESSION_COOKIE_DOMAIN=(config.SESSION_COOKIE_DOMAIN or None),
        SESSION_COOKIE_SAMESITE=getattr(config, "COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=getattr(config, "COOKIE_SECURE", False),
        SESSION_COOKIE_HTTPONLY=True,
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH= 4 * 1024 * 1024 * 1024,  # Upload limit 1 GB
    )

    # ---------------- COMPRESSION SETTINGS (GZIP) ----------------
    # Critical for vector tiles (.pbf) and large JSON responses
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
    # Allow requests only to API
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
    # Important: add url_prefix="/api" everywhere so the frontend can access
    # via /api/orthophotos, /api/panoramas etc.
    
    # 1. Auth (Authorization)
    if auth_blueprint:
        app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    
    # 2. Vector / PostGIS (Vector data)
    if vector_bp:
        app.register_blueprint(vector_bp, url_prefix="/api")

    # 3. Pano (Panoramas)
    if pano_blueprint:
        app.register_blueprint(pano_blueprint, url_prefix="/api")
    
    # 4. Ortho (Orthophotos)
    if ortho_blueprint:
        app.register_blueprint(ortho_blueprint, url_prefix="/api")

    # API Health Check
    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "db": "postgres"})

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

    # Fallback to index.html for SPA (any unknown path returns React app)
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
    # Run on all interfaces (0.0.0.0) so Docker can forward the port
    application.run(host="0.0.0.0", port=5000, debug=True)