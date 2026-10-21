"""Real application/DB smoke test; S3 is replaced so no external storage is accessed."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "server"))


class StorageStub:
    def __init__(self):
        self.client = None
        self.bucket_name = "test-panoramas"


with TemporaryDirectory() as directory:
    os.environ.update({
        "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
        "DB_HOST": "not-used-when-database-url-is-set.invalid",
        "APP_ENV": "testing", "COOKIE_SECURE": "false", "SESSION_COOKIE_DOMAIN": "",
        "SECRET_KEY": "isolated-probe-only", "JWT_SECRET": "isolated-probe-only",
        "DEFAULT_ADMIN_USERNAME": "scope_probe_admin", "DEFAULT_ADMIN_PASSWORD": "isolated-probe-only",
        "DEFAULT_USER_USERNAME": "scope_probe_user", "DEFAULT_USER_PASSWORD": "isolated-probe-only",
        "UPLOAD_FOLDER": directory, "ORTHO_FOLDER": directory,
        "TEMP_FOLDER": directory, "TASKS_FOLDER": directory,
    })
    import storage
    with patch.object(storage, "MinioStorage", StorageStub):
        from init_pg_auth import init_auth_db
        init_auth_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        assert client.get("/api/orthophotos").status_code == 401
        login = client.post("/api/auth/login", json={"username": "scope_probe_admin", "password": "isolated-probe-only"})
        assert login.status_code == 200, login.get_data(as_text=True)
        for path in ["/api/auth/me", "/api/orthophotos", "/api/panoramas", "/api/vector/databases"]:
            response = client.get(path)
            assert response.status_code == 200, (path, response.get_data(as_text=True))
        assert client.get("/api/unknown-endpoint").status_code == 404

        from database import Database
        with Database().cursor() as cursor:
            cursor.execute("SELECT count(*) AS count FROM pg_stat_activity WHERE datname=current_database() AND state LIKE 'idle in transaction%'")
            assert cursor.fetchone()["count"] == 0, "application left idle transactions"
        with patch("app.create_pano_blueprint", side_effect=RuntimeError("required route failed")):
            try:
                create_app()
            except RuntimeError as error:
                assert str(error) == "required route failed"
            else:
                raise AssertionError("application started without required routes")

print("application transaction smoke passed")
