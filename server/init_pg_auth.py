# server/init_pg_auth.py

import os
import psycopg2
from werkzeug.security import generate_password_hash

def init_auth_db():
    print("Connecting to PostgreSQL to init Users...")
    # Получаем URL из переменных окружения (в контейнере он есть)
    # Если запускаете локально без Docker, замените на свой DSN
    dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db")
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # 1. Создаем таблицу users
        print("Creating table 'users' if not exists...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 2. Создаем admin / admin
        cur.execute("SELECT id FROM users WHERE username = %s", ('admin',))
        if not cur.fetchone():
            print("Creating user 'admin'...")
            # Генерируем хеш пароля
            pw_hash = generate_password_hash("admin") 
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('admin', pw_hash))
            print("User 'admin' created! Password: admin")
        else:
            print("User 'admin' already exists.")
        
        conn.commit()
        cur.close()
        conn.close()
        print("Auth Database initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing Auth DB: {e}")

if __name__ == "__main__":
    init_auth_db()