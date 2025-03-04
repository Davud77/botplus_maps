# ./backend/managers/user_manager.py

from models.user import User
from werkzeug.security import generate_password_hash

class UserManager:
    def __init__(self, db):
        self.db = db

    def find_by_username(self, username):
        """
        Ищем пользователя по логину.
        Возвращаем объект User или None.
        """
        cursor = self.db.get_cursor()
        query = "SELECT * FROM users WHERE username = ?"
        cursor.execute(query, (username,))
        row = cursor.fetchone()
        if row:
            user = User(
                user_id=row["id"],
                username=row["username"],
                password=row["password"]
            )
            return user
        return None

    def create_user(self, username, password):
        """
        Создаем пользователя с хешированным паролем.
        """
        cursor = self.db.get_cursor()
        hashed_password = generate_password_hash(password)
        query = "INSERT INTO users (username, password) VALUES (?, ?)"
        cursor.execute(query, (username, hashed_password))
        self.db.commit()

    def find_by_credentials(self, username, password):
        """
        (Не используется напрямую, но если понадобится сравнивать
         пароль в открытом виде - устаревший вариант, лучше check_password_hash)
        """
        cursor = self.db.get_cursor()
        query = "SELECT * FROM users WHERE username = ? AND password = ?"
        cursor.execute(query, (username, password))
        row = cursor.fetchone()
        if row:
            user = User(
                user_id=row["id"],
                username=row["username"],
                password=row["password"]
            )
            return user
        return None