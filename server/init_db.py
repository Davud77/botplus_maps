# Filename: init_db.py
# Path: ./init_db.py

import sqlite3
import config
from werkzeug.security import generate_password_hash

def init_db():
    """
    Создаёт таблицы, используемые приложением, если они ещё не созданы,
    а также добавляет дефолтного пользователя (user/password), храня пароль в виде хеша.
    """
    conn = sqlite3.connect(config.DB_FILE)
    try:
        cursor = conn.cursor()
        
        # Включаем foreign_keys (опционально, улучшает целостность)
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            );
        """)
        
        # Таблица панорам (согласно структуре photos_4326 в PostgreSQL)
        cursor.execute("""
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
        
        # Таблица ортофотографий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ortholist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                bounds TEXT
            );
        """)
        
        # Добавляем дефолтного пользователя, если его ещё нет (пароль будет хеширован)
        cursor.execute("SELECT id FROM users WHERE username = ?", ("user",))
        row = cursor.fetchone()
        if not row:
            hashed_password = generate_password_hash("password")
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                ("user", hashed_password)
            )
            print("Добавлен дефолтный пользователь: user / пароль: 'password' (хранится в хеше).")

        conn.commit()
        print("Инициализация БД завершена. Таблицы созданы (если отсутствовали).")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()