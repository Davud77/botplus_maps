"""Legacy user facade, using isolated PostgreSQL operations."""
try:
    from ..models.user import User
except ImportError:
    from models.user import User
from werkzeug.security import generate_password_hash, check_password_hash


class UserManager:
    def __init__(self, db):
        self.db = db

    def find_by_username(self, username):
        with self.db.cursor() as cursor:
            cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()
        return User(user_id=row["id"], username=row["username"], password=row["password"]) if row else None

    def create_user(self, username, password):
        password_hash = generate_password_hash(password)
        with self.db.cursor(write=True) as cursor:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password_hash))

    def find_by_credentials(self, username, password):
        user = self.find_by_username(username)
        return user if user and check_password_hash(user.password, password) else None
