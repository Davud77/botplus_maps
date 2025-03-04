import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "botplus.db")

# Общая папка для загрузок
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# Папка для панорам
PANO_FOLDER = os.path.join(UPLOAD_FOLDER, "panos")

# Папка для ортофото (исходные TIFF + preview)
ORTHO_FOLDER = os.path.join(UPLOAD_FOLDER, "orthos")

# Папка для предсгенерированных тайлов ортофото (внутри ORTHO_FOLDER)
TILES_FOLDER = os.path.join(ORTHO_FOLDER, "tiles")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PANO_FOLDER, exist_ok=True)
os.makedirs(ORTHO_FOLDER, exist_ok=True)
os.makedirs(TILES_FOLDER, exist_ok=True)

SECRET_KEY = "some-secret-key"