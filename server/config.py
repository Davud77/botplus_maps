# server/config.py
import os
from datetime import timedelta

def _env_bool(name: str, default: bool) -> bool:
    """Безопасный парсинг булевых значений из переменных окружения"""
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

# Базовая директория проекта (папка server)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =======================================================
# 1. РЕЖИМ РАБОТЫ И СЕТЬ
# =======================================================
APP_ENV = os.getenv("APP_ENV", "development")
APP_PORT = int(os.getenv("APP_PORT", 5580))

_default_origins = "http://localhost:5580,http://127.0.0.1:5580,http://localhost:3000,http://127.0.0.1:3000"
CLIENT_ORIGINS = [
    o.strip()
    for o in os.getenv("CLIENT_ORIGINS", _default_origins).split(",")
    if o.strip()
]

# =======================================================
# 2. БЕЗОПАСНОСТЬ (Flask & Auth)
# =======================================================
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-secret")
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)

# Время жизни access-токена (по умолчанию 7 дней)
ACCESS_TOKEN_EXPIRES = int(
    os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS", str(int(timedelta(days=7).total_seconds())))
)

# Настройки Cookie
COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN") or None
SESSION_COOKIE_HTTPONLY = True

# =======================================================
# 3. АДМИНИСТРАТОР
# =======================================================
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "change_me_please")

# =======================================================
# 4. ФАЙЛОВАЯ СИСТЕМА И ПУТИ
# =======================================================
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
ORTHO_FOLDER = os.getenv("ORTHO_FOLDER", os.path.join(UPLOAD_FOLDER, "orthos"))
# Поднимаемся на уровень выше server, чтобы попасть в data
TEMP_FOLDER = os.getenv("TEMP_FOLDER", os.path.join(BASE_DIR, "..", "data", "temp", "orthos"))
TASKS_FOLDER = os.getenv("TASKS_FOLDER", os.path.join(BASE_DIR, "..", "data", "tasks"))

# Внутренние подпапки
PANO_FOLDER = os.path.join(UPLOAD_FOLDER, "panos")
TILES_FOLDER = os.path.join(ORTHO_FOLDER, "tiles")

# Создаём все директории при старте
for d in (UPLOAD_FOLDER, PANO_FOLDER, ORTHO_FOLDER, TILES_FOLDER, TEMP_FOLDER, TASKS_FOLDER):
    os.makedirs(d, exist_ok=True)

# =======================================================
# 5. БАЗА ДАННЫХ (PostgreSQL / PostGIS)
# =======================================================
DB_HOST = os.getenv("DB_HOST", "pgbouncer")
DB_PORT = os.getenv("DB_PORT", "6432")
DB_NAME = os.getenv("DB_NAME", "botplus_db")
DB_USER = os.getenv("DB_USER", "botplus_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "botplus_password")

# Используем готовую строку из .env или собираем резервную
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# =======================================================
# 6. OBJECT STORAGE (MinIO)
# =======================================================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = _env_bool("MINIO_SECURE", False)
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "panoramas")
MINIO_ORTHO_BUCKET = os.getenv("MINIO_ORTHO_BUCKET", "orthophotos")

# =======================================================
# 7. TITILER & GDAL
# =======================================================
TITILER_INTERNAL_URL = os.getenv("TITILER_INTERNAL_URL", "http://titiler:80")