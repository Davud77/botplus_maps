import os
import sqlite3
from werkzeug.security import generate_password_hash

# 1. Настраиваем новый пароль
NEW_PASSWORD = "pyqQu1-xandex-ryjvyc"

# 2. Определяем правильный путь к базе (../data/botplus.db)
# Получаем папку, где лежит этот скрипт (server/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся на уровень выше и заходим в папку data
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "../data/botplus.db"))

print(f"--- Сброс пароля ---")
print(f"Целевая база: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print(f"ОШИБКА: Файл базы данных не найден по пути: {DB_PATH}")
    print("Убедитесь, что скрипт лежит в папке 'server', а база в папке 'data'.")
    exit(1)

# 3. Генерируем хеш
# Используем метод scrypt, как в вашем проекте
new_hash = generate_password_hash(NEW_PASSWORD, method='scrypt')

# 4. Записываем в базу
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Обновляем admin
    cursor.execute("UPDATE users SET password = ? WHERE username = 'admin'", (new_hash,))
    if cursor.rowcount > 0:
        print(f"✅ Пароль для пользователя 'admin' изменен.")
    else:
        # Если админа вдруг нет - создаем
        cursor.execute("INSERT INTO users (username, password) VALUES ('admin', ?)", (new_hash,))
        print(f"✅ Пользователь 'admin' создан с новым паролем.")

    # Обновляем user (резервный вход)
    cursor.execute("UPDATE users SET password = ? WHERE username = 'user'", (new_hash,))
    if cursor.rowcount > 0:
        print(f"✅ Пароль для пользователя 'user' изменен.")

    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"Готово! Ваш новый пароль: {NEW_PASSWORD}")

except Exception as e:
    print(f"❌ Произошла ошибка при работе с базой: {e}")