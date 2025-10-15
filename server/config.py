import os
from datetime import timedelta

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Файл БД (можно переопределить через ENV DB_FILE)
DB_FILE = os.getenv("DB_FILE", os.path.join(BASE_DIR, "botplus.db"))

# Общая папка для загрузок (ENV: UPLOAD_FOLDER)
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))

# Папка для панорам
PANO_FOLDER = os.path.join(UPLOAD_FOLDER, "panos")

# Папка для ортофото (исходные TIFF + preview)
ORTHO_FOLDER = os.path.join(UPLOAD_FOLDER, "orthos")

# Папка для предсгенерированных тайлов ортофото (внутри ORTHO_FOLDER)
TILES_FOLDER = os.path.join(ORTHO_FOLDER, "tiles")

# Создаём директории при старте
for d in (UPLOAD_FOLDER, PANO_FOLDER, ORTHO_FOLDER, TILES_FOLDER):
    os.makedirs(d, exist_ok=True)

# Секреты
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)

# JWT/сессия: время жизни access-токена (сек) — по умолчанию 7 дней
ACCESS_TOKEN_EXPIRES = int(
    os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS", str(int(timedelta(days=7).total_seconds())))
)

# Настройки cookie (в dev — безопасные дефолты; в prod включай Secure и SameSite=None)
COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)          # В проде True
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")      # Для кросс-домена нужно 'None'
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "")  # В dev пусто (localhost)
SESSION_COOKIE_HTTPONLY = True

# Разрешённые origins для CORS (через ENV CLIENT_ORIGINS можно перечислить через запятую)
_default_origins = [
    "http://localhost:5580",
    "http://127.0.0.1:5580",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://botplus.ru",
    "https://api.botplus.ru",
]
CLIENT_ORIGINS = [
    o.strip()
    for o in os.getenv("CLIENT_ORIGINS", ",".join(_default_origins)).split(",")
    if o.strip()
]
