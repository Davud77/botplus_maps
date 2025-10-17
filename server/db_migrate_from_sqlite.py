# server/db_migrate_from_sqlite.py
"""
Одноразовая миграция данных из старой SQLite-базы (data/botplus.db) в PostgreSQL/PostGIS.

Что переносим:
  - users                → users (username/password). Если пароль в SQLite в открытом виде — захешируем.
  - panolist             → panos  (filename, title=None, meta=<прочие поля>, geom из (lon, lat) если заданы)
  - ortholist            → orthos (filename, footprint из bounds, если распарсили)

Поля, которых нет в новой схеме, складываем в JSONB meta (для panos/orthos).

Ожидаемая старая схема SQLite (см. ваш init_db под SQLite):
  users(id, username, password)
  panolist(id, filename, latitude, longitude, user_id, file_type, file_size,
           full_pano_width_pixels, full_pano_height_pixels, first_photo_date,
           model, altitude, focal_length, tags, upload_date)
  ortholist(id, filename, bounds)

Запуск (в контейнере приложения):
  docker exec -it botplus_app python /app/server/db_migrate_from_sqlite.py

Повторные запуски безопасны: перед вставкой проверяем наличие по UNIQUE-признакам (username/filename).
"""

from __future__ import annotations

import os
import json
import sqlite3
from typing import Any, Dict, Optional, Tuple

from werkzeug.security import generate_password_hash
from psycopg2.extras import Json

import config
from database import get_connection


def _sqlite_path() -> str:
    """
    Определяем путь к SQLite: берём ENV DB_FILE (если задан),
    иначе <config.DATA_DIR>/botplus.db
    """
    legacy = os.getenv("DB_FILE")
    if legacy and os.path.exists(legacy):
        return legacy
    return os.path.join(config.DATA_DIR, "botplus.db")


# ----------------------------- helpers -----------------------------

def _table_exists_sqlite(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? COLLATE NOCASE",
        (table,),
    )
    return cur.fetchone() is not None


def _try_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _parse_bounds(bounds: Optional[str]) -> Tuple[Optional[str], Optional[Tuple[float, float, float, float]]]:
    """
    Пытаемся распарсить bounds из ortholist в одно из представлений:
      1) WKT (POLYGON/MULTIPOLYGON/LINESTRING/POINT/GEOMETRYCOLLECTION)
         -> вернём ('wkt', None), сам wkt подставим через ST_GeomFromText.
      2) GeoJSON (строка JSON) -> ('geojson', None)
      3) CSV bbox: "minx,miny,maxx,maxy"
         -> (None, (minx,miny,maxx,maxy)) для ST_MakeEnvelope

    Если распарсить не удалось — вернём (None, None).
    """
    if not bounds:
        return (None, None)

    b = bounds.strip()
    # Популярные префиксы WKT
    wkt_prefixes = ("POLYGON", "MULTIPOLYGON", "LINESTRING", "POINT", "GEOMETRYCOLLECTION")
    if any(b.upper().startswith(pref) for pref in wkt_prefixes):
        return ("wkt", None)

    # Похоже на JSON (GeoJSON)?
    if (b.startswith("{") and b.endswith("}")) or (b.startswith("[") and b.endswith("]")):
        try:
            obj = json.loads(b)
            if isinstance(obj, dict) and "type" in obj:
                return ("geojson", None)
        except Exception:
            pass  # не GeoJSON

    # Попробуем csv bbox
    parts = [p.strip() for p in b.replace("bbox", "").replace("(", "").replace(")", "").split(",")]
    if len(parts) == 4:
        nums = []
        for p in parts:
            v = _try_float(p)
            if v is None:
                nums = []
                break
            nums.append(v)
        if len(nums) == 4:
            minx, miny, maxx, maxy = nums
            if minx < maxx and miny < maxy:
                return (None, (minx, miny, maxx, maxy))

    return (None, None)


# ----------------------------- migrations -----------------------------

def migrate_users(sqlite_conn: sqlite3.Connection, verbose: bool = True) -> int:
    if not _table_exists_sqlite(sqlite_conn, "users"):
        if verbose:
            print("SQLite: таблица users не найдена — пропускаем.")
        return 0

    sc = sqlite_conn.cursor()
    sc.row_factory = sqlite3.Row
    sc.execute("SELECT username, password FROM users")
    rows = sc.fetchall()

    inserted = 0
    with get_connection() as pg_conn:
        pc = pg_conn.cursor()
        for r in rows:
            username = str(r["username"]).strip()
            password = r["password"]
            if not username:
                continue

            pc.execute("SELECT 1 FROM users WHERE username=%s", (username,))
            if pc.fetchone():
                continue

            # Если пароль в SQLite не выглядит как werkzeug-hash, захешируем.
            pwd = str(password) if password is not None else ""
            if not pwd.startswith("pbkdf2:"):
                pwd = generate_password_hash(pwd or "password")

            pc.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, pwd),
            )
            inserted += 1

    if verbose:
        print(f"Перенесено пользователей: {inserted}")
    return inserted


def migrate_panos(sqlite_conn: sqlite3.Connection, verbose: bool = True) -> int:
    if not _table_exists_sqlite(sqlite_conn, "panolist"):
        if verbose:
            print("SQLite: таблица panolist не найдена — пропускаем.")
        return 0

    sc = sqlite_conn.cursor()
    sc.row_factory = sqlite3.Row
    sc.execute("SELECT * FROM panolist")
    rows = sc.fetchall()

    inserted = 0
    with get_connection() as pg_conn:
        pc = pg_conn.cursor()
        for r in rows:
            filename = (r["filename"] or "").strip()
            if not filename:
                continue

            # Проверим, есть ли уже запись с таким filename
            pc.execute("SELECT id FROM panos WHERE filename=%s", (filename,))
            if pc.fetchone():
                continue

            # Собираем meta из всех полей, кроме filename/lat/lon
            skip_keys = {"id", "filename", "latitude", "longitude"}
            meta: Dict[str, Any] = {}
            for k in r.keys():
                if k not in skip_keys:
                    meta[k] = r[k]

            lat = _try_float(r["latitude"])
            lon = _try_float(r["longitude"])

            if lat is not None and lon is not None:
                # c геометрией
                pc.execute(
                    """
                    INSERT INTO panos (filename, title, meta, geom)
                    VALUES (%s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326))
                    """,
                    (filename, None, Json(meta), lon, lat),
                )
            else:
                # без геометрии
                pc.execute(
                    "INSERT INTO panos (filename, title, meta) VALUES (%s, %s, %s)",
                    (filename, None, Json(meta)),
                )
            inserted += 1

    if verbose:
        print(f"Перенесено панорам из panolist → panos: {inserted}")
    return inserted


def migrate_orthos(sqlite_conn: sqlite3.Connection, verbose: bool = True) -> int:
    if not _table_exists_sqlite(sqlite_conn, "ortholist"):
        if verbose:
            print("SQLite: таблица ortholist не найдена — пропускаем.")
        return 0

    sc = sqlite_conn.cursor()
    sc.row_factory = sqlite3.Row
    sc.execute("SELECT * FROM ortholist")
    rows = sc.fetchall()

    inserted = 0
    with get_connection() as pg_conn:
        pc = pg_conn.cursor()
        for r in rows:
            filename = (r["filename"] or "").strip()
            if not filename:
                continue

            pc.execute("SELECT id FROM orthos WHERE filename=%s", (filename,))
            if pc.fetchone():
                continue

            bounds = r["bounds"]
            flavor, bbox = _parse_bounds(bounds)

            if flavor == "wkt":
                # bounds — это WKT
                pc.execute(
                    """
                    INSERT INTO orthos (filename, footprint)
                    VALUES (%s, ST_SetSRID(ST_GeomFromText(%s), 4326))
                    """,
                    (filename, bounds),
                )
            elif flavor == "geojson":
                # bounds — это GeoJSON
                pc.execute(
                    """
                    INSERT INTO orthos (filename, footprint)
                    VALUES (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    """,
                    (filename, bounds),
                )
            elif bbox is not None:
                # bounds — это bbox "minx,miny,maxx,maxy"
                minx, miny, maxx, maxy = bbox
                pc.execute(
                    """
                    INSERT INTO orthos (filename, footprint)
                    VALUES (%s, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
                    """,
                    (filename, minx, miny, maxx, maxy),
                )
            else:
                # Не смогли распарсить — вставим без footprint
                pc.execute("INSERT INTO orthos (filename) VALUES (%s)", (filename,))

            inserted += 1

    if verbose:
        print(f"Перенесено ортофото из ortholist → orthos: {inserted}")
    return inserted


def main():
    sqlite_file = _sqlite_path()
    if not os.path.exists(sqlite_file):
        print(f"SQLite-файл не найден: {sqlite_file}")
        return

    print(f"Читаем SQLite: {sqlite_file}")
    sqlite_conn = sqlite3.connect(sqlite_file)
    try:
        sqlite_conn.row_factory = sqlite3.Row

        total_users = migrate_users(sqlite_conn)
        total_panos = migrate_panos(sqlite_conn)
        total_orthos = migrate_orthos(sqlite_conn)

        print("Миграция завершена.")
        print(f"  users:   +{total_users}")
        print(f"  panos:   +{total_panos}")
        print(f"  orthos:  +{total_orthos}")
        print("Готово.")
    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    main()
