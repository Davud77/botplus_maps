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

            cur.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'viewer'")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0")
            cur.execute("ALTER TABLE app_installation ADD COLUMN IF NOT EXISTS rbac_migrated BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("SELECT rbac_migrated FROM app_installation WHERE id=1")
            installation = cur.fetchone()
            if installation and not installation[0]:
                cur.execute("""UPDATE users SET role='admin' WHERE id=(SELECT min(id) FROM users)
                    AND NOT EXISTS (SELECT 1 FROM users WHERE role='admin' AND is_active)""")
                cur.execute("UPDATE users SET role='viewer' WHERE role NOT IN ('admin','editor','viewer')")
                cur.execute("UPDATE app_installation SET rbac_migrated=TRUE WHERE id=1")
            cur.execute("""CREATE TABLE IF NOT EXISTS maps (
                id UUID PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
                title VARCHAR(120) NOT NULL, description VARCHAR(1000) NOT NULL DEFAULT '',
                config JSONB NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                public_slug VARCHAR(64) UNIQUE, published_snapshot JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute("CREATE INDEX IF NOT EXISTS maps_owner_idx ON maps(owner_id)")

            from services.map_settings import initialize_catalogs
            initialize_catalogs(cur)
            from import_jobs import initialize
            initialize(cur)

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

            from controllers.media_catalog import initialize as initialize_media
            initialize_media(cur)
            from controllers.data_import import initialize as initialize_import_catalog
            initialize_import_catalog(cur)

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
