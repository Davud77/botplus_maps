"""Allocate storage keys independently of client paths and concurrent filenames."""
from pathlib import PurePosixPath
from uuid import uuid4
from werkzeug.utils import secure_filename


def ortho_upload_key(client_filename):
    name = PurePosixPath((client_filename or "").replace("\\", "/"))
    suffix = name.suffix.lower()
    if suffix not in {".tif", ".tiff"}:
        raise ValueError("Ожидается GeoTIFF (.tif или .tiff)")
    # Cyrillic/non-ASCII names remain uploadable even when transliteration is empty.
    stem = secure_filename(name.stem)[:160] or "orthophoto"
    return f"{uuid4().hex}_{stem}{suffix}"
