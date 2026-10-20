import unittest
from flask import Flask, Response, jsonify
from server.http_policies import register_http_policies


class HttpPolicyTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_http_policies(app, lambda token: {"uid": 1} if token == "valid" else None,
                               lambda origin: origin == "http://localhost:3000")
        app.add_url_rule("/api/health", endpoint="route_1", view_func=lambda: jsonify(ok=True))
        app.add_url_rule("/api/auth/login", endpoint="route_2", view_func=lambda: jsonify(ok=True), methods=["POST"])
        app.add_url_rule("/api/upload", endpoint="route_3", view_func=lambda: jsonify(ok=True), methods=["POST"])
        app.add_url_rule("/api/vector/create_db", endpoint="route_4", view_func=lambda: jsonify(ok=True), methods=["POST"])
        app.add_url_rule("/api/orthophotos/1", endpoint="route_5", view_func=lambda: jsonify(ok=True), methods=["DELETE"])
        app.add_url_rule("/api/catalog", endpoint="route_6", view_func=lambda: jsonify(ok=True))
        app.add_url_rule("/api/orthophotos/1/tiles/1/0/0.png", endpoint="route_7", view_func=lambda: Response(b"tile", mimetype="image/png"))
        app.add_url_rule("/api/broken/tiles/1/0/0.png", endpoint="route_8", view_func=lambda: (jsonify(error="upstream"), 502))
        app.add_url_rule("/static/app.js", endpoint="script", view_func=lambda: Response("code", headers={"Cache-Control": "public, max-age=31536000"}))
        self.client = app.test_client()

    def authenticate(self):
        self.client.set_cookie("access_token", "valid")

    def test_anonymous_mutations_are_rejected(self):
        for method, url in [("POST", "/api/upload"), ("POST", "/api/vector/create_db"), ("DELETE", "/api/orthophotos/1")]:
            response = self.client.open(url, method=method)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_health_and_login_are_reachable(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/login").status_code, 200)

    def test_invalid_cookie_is_rejected(self):
        self.client.set_cookie("access_token", "invalid")
        self.assertEqual(self.client.get("/api/catalog").status_code, 401)

    def test_cross_site_mutation_is_rejected_with_valid_session(self):
        self.authenticate()
        self.assertEqual(self.client.post("/api/upload", headers={"Origin": "https://untrusted.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/api/upload", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.post("/api/upload", headers={"Origin": "http://localhost:3000"}).status_code, 200)

    def test_private_tiles_can_be_cached_without_shared_cache(self):
        self.authenticate()
        response = self.client.get("/api/orthophotos/1/tiles/1/0/0.png")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cache_control.private)
        self.assertEqual(response.cache_control.max_age, 60)
        self.assertIn("Cookie", response.vary)
        self.assertFalse(response.cache_control.no_store)

    def test_metadata_and_failed_tiles_are_not_cached(self):
        self.authenticate()
        for url in ["/api/catalog", "/api/broken/tiles/1/0/0.png"]:
            self.assertTrue(self.client.get(url).cache_control.no_store)

    def test_static_cache_policy_is_preserved(self):
        self.assertEqual(self.client.get("/static/app.js").cache_control.max_age, 31536000)
