# server/init_pg_auth.py

import os
import psycopg2
from werkzeug.security import generate_password_hash

def init_auth_db():
    print("Connecting to PostgreSQL to initialize all tables...")
    # Получаем URL из переменных окружения (в контейнере он есть)
    dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db")
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
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
        
        # 4. Создаем дефолтного администратора
        # Получаем данные из .env, если их нет — используем безопасные fallback-значения
        admin_username = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "change_me_please")
        
        cur.execute("SELECT id FROM users WHERE username = %s", (admin_username,))
        if not cur.fetchone():
            print(f"Creating user '{admin_username}'...")
            pw_hash = generate_password_hash(admin_password) 
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (admin_username, pw_hash))
            print(f"User '{admin_username}' successfully created!")
            
        # 5. Создаем дефолтного обычного пользователя
        # Получаем данные из .env, если их нет — используем fallback-значения
        user_username = os.environ.get("DEFAULT_USER_USERNAME", "user")
        user_password = os.environ.get("DEFAULT_USER_PASSWORD", "password")
        
        cur.execute("SELECT id FROM users WHERE username = %s", (user_username,))
        if not cur.fetchone():
            print(f"Creating user '{user_username}'...")
            user_pw_hash = generate_password_hash(user_password)
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (user_username, user_pw_hash))
            print(f"User '{user_username}' successfully created!")
        
        conn.commit()
        cur.close()
        conn.close()
        print("All tables and default users initialized successfully!")
        
    except Exception as e:
        print(f"Error during Database initialization: {e}")

if __name__ == "__main__":
    init_auth_db()