# server/init_db.py
"""
Инициализация PostgreSQL/PostGIS-схемы для Botplus.

Создаёт:
  - расширение postgis (если отсутствует);
  - таблицы users, panos, orthos;
  - индексы GIST по геометриям;
  - администратора (имя/пароль берутся из ENV или дефолтов: newadmin / New#Pass123);
  - совместимые представления (VIEW) panolist и ortholist для лёгаси-кода.

Запускается идемпотентно (IF NOT EXISTS / OR REPLACE, UPSERT по пользователю).
"""

import os
from werkzeug.security import generate_password_hash
from database import get_connection

DDL = [
    # Расширение PostGIS
    "CREATE EXTENSION IF NOT EXISTS postgis",

    # Таблица пользователей
    """
    CREATE TABLE IF NOT EXISTS users (
        id          SERIAL PRIMARY KEY,
        username    TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # Панорамы: точка в WGS84 + произвольные метаданные
    """
    CREATE TABLE IF NOT EXISTS panos (
        id          SERIAL PRIMARY KEY,
        filename    TEXT NOT NULL,
        title       TEXT,
        meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
        geom        geometry(Point, 4326),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS panos_gix ON panos USING GIST (geom)",

    # Ортофото: полигон в WGS84 (границы/контур) + метаданные
    """
    CREATE TABLE IF NOT EXISTS orthos (
        id          SERIAL PRIMARY KEY,
        filename    TEXT NOT NULL,
        preview     TEXT,
        meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
        footprint   geometry(Polygon, 4326),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS orthos_gix ON orthos USING GIST (footprint)",

    # ------- Легаси-совместимость (VIEW) -------
    # panolist: filename + широта/долгота из geom; остальные старые поля — NULL.
    """
    CREATE OR REPLACE VIEW panolist AS
    SELECT
        p.id,
        p.filename,
        ST_Y(p.geom) AS latitude,
        ST_X(p.geom) AS longitude,
        NULL::INTEGER AS user_id,
        NULL::TEXT    AS file_type,
        NULL::BIGINT  AS file_size,
        NULL::INTEGER AS full_pano_width_pixels,
        NULL::INTEGER AS full_pano_height_pixels,
        NULL::TEXT    AS first_photo_date,
        NULL::TEXT    AS model,
        NULL::DOUBLE PRECISION AS altitude,
        NULL::DOUBLE PRECISION AS focal_length,
        NULL::TEXT    AS tags,
        p.created_at::TEXT AS upload_date
    FROM panos p
    """,

    # ortholist: filename + bounds (WKT envelope от footprint)
    """
    CREATE OR REPLACE VIEW ortholist AS
    SELECT
        o.id,
        o.filename,
        CASE
          WHEN o.footprint IS NOT NULL THEN ST_AsText(ST_Envelope(o.footprint))
          ELSE NULL
        END AS bounds
    FROM orthos o
    """,
]


def ensure_admin_user():
    """
    Создаёт/обновляет администратора.
    Имя/пароль читаются из окружения:
      ADMIN_USERNAME (default: newadmin)
      ADMIN_PASSWORD (default: New#Pass123)
    Если пользователь существует — пароль будет обновлён.
    """
    username = os.getenv("ADMIN_USERNAME", "newadmin").strip()
    password = os.getenv("ADMIN_PASSWORD", "New#Pass123")

    if not username:
        raise ValueError("ADMIN_USERNAME пустой — укажите корректное имя пользователя")

    hashed = generate_password_hash(password or "")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (username, password)
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE
              SET password = EXCLUDED.password
            """,
            (username, hashed),
        )


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        for stmt in DDL:
            cur.execute(stmt)

    ensure_admin_user()
    print("PostgreSQL/PostGIS: схема инициализирована, индексы созданы, VIEW обновлены, администратор настроен.")


if __name__ == "__main__":
    init_db()
