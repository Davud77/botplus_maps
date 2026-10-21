# server/init_pg_auth.py

import os
try:
    from .database import Database
except ImportError:
    from database import Database


def init_auth_db():
    print("Connecting to PostgreSQL to initialize all tables...")
    # Получаем URL из переменных окружения (в контейнере он есть)
    dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db")

    try:
        with Database(dsn).cursor(write=True, dict_rows=False) as cur:

            cur.execute("SELECT pg_advisory_xact_lock(941027001)")

            # 1. Создаем таблицу пользователей
            print("Creating table 'users'...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'")

            cur.execute("""CREATE TABLE IF NOT EXISTS app_installation (
                id INTEGER PRIMARY KEY CHECK (id = 1), initialized_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("""INSERT INTO app_installation (id) SELECT 1 WHERE EXISTS (SELECT 1 FROM users)
                ON CONFLICT (id) DO NOTHING""")

            # 2. Создаем таблицу панорам (photos_4326)
            # ВАЖНО: Требует расширения PostGIS в базе данных
            print("Creating table 'public.photos_4326'...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.photos_4326 (
                    id SERIAL PRIMARY KEY,
                    geom geometry(PointZ, 4326),
                    path VARCHAR,
                    filename VARCHAR,
                    directory VARCHAR,
                    altitude NUMERIC,
                    direction NUMERIC,
                    rotation INTEGER,
                    longitude VARCHAR,
                    latitude VARCHAR,
                    "timestamp" TIMESTAMP,
                    "order" INTEGER
                );
            """)

            # 3. Создаем таблицу ортофотографий (ortholist)
            print("Creating table 'ortholist'...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ortholist (
                    id SERIAL PRIMARY KEY,
                    filename TEXT,
                    bounds TEXT
                );
            """)

        print("All tables initialized successfully; first account is configured in the browser.")

    except Exception as e:
        print("Database initialization failed")
        raise

if __name__ == "__main__":
    init_auth_db()
