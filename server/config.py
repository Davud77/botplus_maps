# server/config.py
import os
from datetime import timedelta
from urllib.parse import urlparse


def _env_bool(name: str, default: bool) -> bool:
    """Безопасное чтение булевых ENV: 1/true/yes/y/on → True."""
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_csv(name: str, default_list: list[str]) -> list[str]:
    """Чтение списков из ENV с разделителем-запятой."""
    raw = os.getenv(name)
    if not raw:
        return default_list
    return [item.strip() for item in raw.split(",") if item.strip()]


# ====================== Paths & Storage ======================

# Директория с этим файлом (обычно: server/)
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
# Корень репозитория (на один уровень выше)
_REPO_ROOT = os.path.abspath(os.path.join(_SERVER_DIR, os.pardir))

# Общая директория для персистентных данных (медиа, кеши и т.п.)
DATA_DIR = os.getenv("DATA_DIR", os.path.join(_REPO_ROOT, "data"))

# Папка со статикой/SPA (по умолчанию <repo>/public); можно переопределить PUBLIC_DIR
PUBLIC_DIR = os.path.abspath(os.getenv("PUBLIC_DIR", os.path.join(_REPO_ROOT, "public")))

# Центральная директория для медиафайлов.
# Приоритет переопределений:
#   1) MEDIA_ROOT (новая переменная)
#   2) UPLOAD_FOLDER (легаси-имя, для совместимости)
#   3) <DATA_DIR>/media (дефолт)
_media_root_env = os.getenv("MEDIA_ROOT")
if _media_root_env:
    MEDIA_ROOT = _media_root_env
else:
    _legacy_upload = os.getenv("UPLOAD_FOLDER")
    MEDIA_ROOT = _legacy_upload if _legacy_upload else os.path.join(DATA_DIR, "media")
MEDIA_ROOT = os.path.abspath(MEDIA_ROOT)

# Доменные подпапки медиа
PANOS_DIR = os.path.join(MEDIA_ROOT, "panos")     # исходники панорам
ORTHOS_DIR = os.path.join(MEDIA_ROOT, "orthos")   # ортофото (tiff/jpeg/preview)
TILES_DIR = os.path.join(ORTHOS_DIR, "tiles")     # предсгенерённые тайлы

# Создаём директории при старте (идемпотентно)
for d in (DATA_DIR, MEDIA_ROOT, PANOS_DIR, ORTHOS_DIR, TILES_DIR):
    os.makedirs(d, exist_ok=True)

# ------- Backward compatibility (старые имена, чтобы не ломать импорты) -------
UPLOAD_FOLDER = MEDIA_ROOT
PANO_FOLDER = PANOS_DIR
ORTHO_FOLDER = ORTHOS_DIR
TILES_FOLDER = TILES_DIR


# ====================== App / Server ======================

APP_NAME = os.getenv("APP_NAME", "botplus")
APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
DEBUG = _env_bool("DEBUG", APP_ENV != "production")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ограничение размера загрузок (по умолчанию 200 МБ)
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(200 * 1024 * 1024)))

# Разрешённые расширения для загрузок
ALLOWED_EXTENSIONS = _env_csv(
    "ALLOWED_EXTENSIONS",
    ["jpg", "jpeg", "png", "webp", "tif", "tiff", "gif", "mp4", "mov", "avi"],
)


# ====================== Secrets & Auth ======================

# Базовый секрет Flask
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

# Если JWT_SECRET не задан — используем SECRET_KEY
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)

# Время жизни access-токена (сек) — по умолчанию 7 дней
ACCESS_TOKEN_EXPIRES = int(
    os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS", str(int(timedelta(days=7).total_seconds())))
)

# Время жизни refresh-токена (сек) — по умолчанию 30 дней
REFRESH_TOKEN_EXPIRES = int(
    os.getenv("REFRESH_TOKEN_EXPIRES_SECONDS", str(int(timedelta(days=30).total_seconds())))
)

# Имена куки для токенов (если используете cookie-based auth)
AUTH_ACCESS_COOKIE = os.getenv("AUTH_ACCESS_COOKIE", "access_token")
AUTH_REFRESH_COOKIE = os.getenv("AUTH_REFRESH_COOKIE", "weam_refresh")

# Флаги безопасности cookie
# В dev можно оставить Secure=False и SameSite=Lax; в проде — Secure=True и SameSite=None.
COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)              # в проде True
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")          # для кросс-домена — 'None'
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "") # в dev пусто (localhost)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", f"{APP_NAME}_session")


# ====================== CORS ======================

_default_origins = [
    "http://localhost:5580",
    "http://127.0.0.1:5580",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://botplus.ru",
    "https://api.botplus.ru",
]
CLIENT_ORIGINS = _env_csv("CLIENT_ORIGINS", _default_origins)

CORS_SUPPORTS_CREDENTIALS = _env_bool("CORS_SUPPORTS_CREDENTIALS", True)
CORS_ALLOW_HEADERS = _env_csv(
    "CORS_ALLOW_HEADERS",
    [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
)
# Ресурсы, на которые разрешаем CORS (если используете flask-cors)
CORS_RESOURCES = {r"/api/*": {"origins": CLIENT_ORIGINS}}


# ====================== Database (PostgreSQL/PostGIS) ======================

# Ожидаем строку вида: postgresql://user:pass@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://botplus:botplus@db:5432/botplus")

def _parse_database_url(dsn: str) -> dict:
    u = urlparse(dsn)
    return {
        "dbname": (u.path or "").lstrip("/"),
        "user": u.username or "",
        "password": u.password or "",
        "host": u.hostname or "localhost",
        "port": int(u.port or 5432),
        "scheme": u.scheme,
    }

DB_PARAMS = _parse_database_url(DATABASE_URL)

# Удобная строка для psycopg2 (dsn)
DATABASE_DSN = (
    f"dbname={DB_PARAMS['dbname']} "
    f"user={DB_PARAMS['user']} "
    f"password={DB_PARAMS['password']} "
    f"host={DB_PARAMS['host']} "
    f"port={DB_PARAMS['port']}"
)


# ====================== Misc / Feature flags ======================

# Включение превью генерируемых тайлов ортофото при загрузке
ENABLE_ORTHO_TILES = _env_bool("ENABLE_ORTHO_TILES", True)

# Включение минимальной валидации имён файлов при загрузке
STRICT_UPLOAD_FILENAMES = _env_bool("STRICT_UPLOAD_FILENAMES", True)


# ====================== Export control ======================

__all__ = [
    # Paths
    "DATA_DIR", "MEDIA_ROOT", "PUBLIC_DIR",
    "PANOS_DIR", "ORTHOS_DIR", "TILES_DIR",
    "UPLOAD_FOLDER", "PANO_FOLDER", "ORTHO_FOLDER", "TILES_FOLDER",
    # App
    "APP_NAME", "APP_ENV", "DEBUG", "HOST", "PORT", "LOG_LEVEL",
    "MAX_CONTENT_LENGTH", "ALLOWED_EXTENSIONS",
    # Secrets/Auth
    "SECRET_KEY", "JWT_SECRET",
    "ACCESS_TOKEN_EXPIRES", "REFRESH_TOKEN_EXPIRES",
    "AUTH_ACCESS_COOKIE", "AUTH_REFRESH_COOKIE",
    "COOKIE_SECURE", "COOKIE_SAMESITE", "SESSION_COOKIE_DOMAIN",
    "SESSION_COOKIE_HTTPONLY", "SESSION_COOKIE_NAME",
    # CORS
    "CLIENT_ORIGINS", "CORS_SUPPORTS_CREDENTIALS",
    "CORS_ALLOW_HEADERS", "CORS_RESOURCES",
    # DB
    "DATABASE_URL", "DB_PARAMS", "DATABASE_DSN",
    # Flags
    "ENABLE_ORTHO_TILES", "STRICT_UPLOAD_FILENAMES",
]
