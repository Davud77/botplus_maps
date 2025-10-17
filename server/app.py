# server/app.py

from flask import Flask, request, send_from_directory, jsonify, make_response, Response
from flask_cors import CORS
from pathlib import Path
import os
import re
import requests
import config

# DB health/ping
try:
    from database import get_connection
except Exception:  # на случай ранних стадий сборки
    get_connection = None  # type: ignore

# --- Optional blueprints (app runs even if some are missing) ---
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

# --- Static paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR   = Path(getattr(config, "PUBLIC_DIR", PROJECT_ROOT / "public"))
BUILD_DIR    = PUBLIC_DIR / "build"

# --- CORS allow-list (strings + regex) ---
ALLOWED_ORIGIN_STRINGS = list(getattr(config, "CLIENT_ORIGINS", ["http://localhost:5580"]))
ALLOWED_ORIGIN_REGEXES = [
    re.compile(r"^https://.*\.botplus\.ru$"),
]

# --- Upstream proxy (to bypass browser CORS by using same-origin /api/*) ---
UPSTREAM_API              = getattr(config, "UPSTREAM_API", "https://api.botplus.ru").rstrip("/")
PROXY_API_ENABLED         = bool(getattr(config, "PROXY_API_ENABLED", True))
PROXY_TIMEOUT             = int(getattr(config, "PROXY_TIMEOUT", 120))  # seconds
PROXY_PASSTHROUGH_HEADERS = {
    "Content-Type",
    "Content-Length",
    "Content-Disposition",
    "Cache-Control",
    "Last-Modified",
    "ETag",
    "Accept-Ranges",
    "Content-Range",
}


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        # Allow tools like curl/Postman (no Origin header)
        return True
    if origin in ALLOWED_ORIGIN_STRINGS:
        return True
    for rx in ALLOWED_ORIGIN_REGEXES:
        if rx.match(origin):
            return True
    return False


def create_app():
    app = Flask(__name__, static_folder=None)
    app.secret_key = config.SECRET_KEY

    # Basic config
    app.config.update(
        MAX_CONTENT_LENGTH=getattr(config, "MAX_CONTENT_LENGTH", 200 * 1024 * 1024),
        JSON_AS_ASCII=False,
        SESSION_COOKIE_HTTPONLY=getattr(config, "SESSION_COOKIE_HTTPONLY", True),
        SESSION_COOKIE_SAMESITE=getattr(config, "COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=getattr(config, "COOKIE_SECURE", False),
        SESSION_COOKIE_NAME=getattr(config, "SESSION_COOKIE_NAME", "botplus_session"),
    )
    if getattr(config, "SESSION_COOKIE_DOMAIN", ""):
        app.config["SESSION_COOKIE_DOMAIN"] = config.SESSION_COOKIE_DOMAIN

    # --- CORS (primary) ---
    cors_resources = getattr(
        config,
        "CORS_RESOURCES",
        {r"/api/*": {"origins": ALLOWED_ORIGIN_STRINGS}},
    )
    CORS(
        app,
        resources=cors_resources,
        origins=ALLOWED_ORIGIN_STRINGS,
        supports_credentials=getattr(config, "CORS_SUPPORTS_CREDENTIALS", True),
        allow_headers=getattr(
            config,
            "CORS_ALLOW_HEADERS",
            ["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token"],
        ),
        expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        vary_header=True,
    )

    @app.after_request
    def ensure_cors_headers(resp: Response):
        """
        Make sure API responses carry proper CORS headers (esp. for requests without
        Origin, like curl/Postman). Mirrors Origin if allowed (credentials-safe).
        """
        path = request.path or ""
        if not path.startswith("/api/"):
            return resp

        origin = request.headers.get("Origin")
        if origin_allowed(origin):
            if origin:
                resp.headers.setdefault("Access-Control-Allow-Origin", origin)
                vary = resp.headers.get("Vary", "")
                vary_parts = {p.strip() for p in vary.split(",") if p.strip()}
                vary_parts.add("Origin")
                resp.headers["Vary"] = ", ".join(sorted(vary_parts))
            resp.headers.setdefault("Access-Control-Allow-Credentials", "true")
            resp.headers.setdefault(
                "Access-Control-Allow-Headers",
                ", ".join(
                    getattr(
                        config,
                        "CORS_ALLOW_HEADERS",
                        ["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token"],
                    )
                ),
            )
            resp.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
            resp.headers.setdefault("Access-Control-Expose-Headers", "Content-Type, Authorization, Content-Disposition")
        return resp

    # --- Fast path for CORS preflight on /api/* ---
    @app.route("/api/<path:_preflight_any>", methods=["OPTIONS"])
    def preflight_ok(_preflight_any: str):
        # 204 with CORS headers (added by after_request)
        return ("", 204)

    # ---------------- Register blueprints ----------------
    if auth_blueprint:
        app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    if pano_blueprint:
        app.register_blueprint(pano_blueprint, url_prefix="/api")
    if ortho_blueprint:
        app.register_blueprint(ortho_blueprint, url_prefix="/api")

    # ---------------- Health ----------------
    @app.get("/api/health")
    def health():
        """
        Быстрый healthcheck + мягкая проверка БД и PostGIS.
        Не падает, если БД ещё не инициализирована (возвращает db_ok=False).
        """
        db_ok = False
        postgis_enabled = False
        if get_connection is not None:
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    db_ok = True
                    # Проверяем наличие расширения postgis (без ошибки, если нет)
                    cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis') AS exists")
                    row = cur.fetchone()
                    # row может быть dict (RealDictCursor) или tuple — поддержим оба случая
                    if isinstance(row, dict):
                        postgis_enabled = bool(row.get("exists"))
                    else:
                        postgis_enabled = bool(row[0]) if row else False
            except Exception:
                db_ok = False
                postgis_enabled = False

        return jsonify({"ok": True, "db_ok": db_ok, "postgis": postgis_enabled})

    # ---------------- Generic reverse proxy for /api/* ----------------
    # This lets the frontend call same-origin /api/... while we forward to UPSTREAM_API.
    # Blueprints take precedence; this is a catch-all for anything not handled above.
    if PROXY_API_ENABLED:
        @app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        def proxy_api(path: str):
            upstream_url = f"{UPSTREAM_API}/{path}"

            # Build headers to forward (strip hop-by-hop/unsafe headers)
            incoming_headers = {}
            for k, v in request.headers.items():
                lk = k.lower()
                if lk in {"host", "content-length", "content-encoding", "transfer-encoding", "connection"}:
                    continue
                # Do not forward Origin to upstream to avoid upstream CORS quirks
                if lk == "origin":
                    continue
                incoming_headers[k] = v

            try:
                resp = requests.request(
                    method=request.method,
                    url=upstream_url,
                    params=request.args,
                    data=request.get_data(),
                    files=None,  # при необходимости можно смэппить form/files
                    headers=incoming_headers,
                    cookies=request.cookies,
                    timeout=PROXY_TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                )
            except requests.RequestException as e:
                return jsonify({"ok": False, "error": f"Upstream request failed: {e}"}), 502

            # Build Flask response
            proxy_resp = make_response(resp.raw.read(), resp.status_code)

            # Pass-through selected headers (content type, disposition, etc.)
            for h, val in resp.headers.items():
                if h in PROXY_PASSTHROUGH_HEADERS:
                    proxy_resp.headers[h] = val

            # Never leak upstream CORS headers; local CORS is added in after_request.
            for h in list(proxy_resp.headers.keys()):
                if h.lower().startswith("access-control-allow-") or h.lower() == "vary":
                    proxy_resp.headers.pop(h, None)

            return proxy_resp

    # ---------------- Static / SPA ----------------
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

    # SPA fallback for non-API routes
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
    application.run(
        host=getattr(config, "HOST", "0.0.0.0"),
        port=int(getattr(config, "PORT", 5000)),
        debug=getattr(config, "DEBUG", False),
    )
