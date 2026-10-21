"""Shared HTTP security and cache rules, without importing storage or database code."""
from flask import g, jsonify, request


def register_http_policies(app, decode_token, origin_allowed):
    public_endpoints = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me",
                        "/api/setup/status", "/api/setup/initialize"}

    @app.before_request
    def protect_api():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None
        if request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("Origin")
            if ((origin and origin != request.host_url.rstrip("/") and not origin_allowed(origin))
                    or request.headers.get("Sec-Fetch-Site") == "cross-site"):
                return jsonify(error="Untrusted request origin"), 403
        if request.path in public_endpoints:
            return None
        payload = decode_token(request.cookies.get("access_token", ""))
        if not payload or not isinstance(payload.get("uid"), int) or payload["uid"] <= 0:
            return jsonify(error="Authentication required"), 401
        g.current_user_id = payload["uid"]
        return None

    @app.after_request
    def apply_cache_policy(response):
        if request.path.startswith("/api/"):
            is_tile = ("/tiles/" in request.path
                       and response.mimetype in {"image/png", "application/vnd.mapbox-vector-tile"})
            if is_tile and request.method in {"GET", "HEAD"} and response.status_code == 200:
                # Legacy URLs are not versioned yet. Never share authenticated tiles in a public cache.
                response.headers["Cache-Control"] = "private, max-age=60"
                response.vary.add("Cookie")
            else:
                response.headers["Cache-Control"] = "no-store"
        return response
