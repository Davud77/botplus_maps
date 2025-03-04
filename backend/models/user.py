# ./backend/models/user.py

class User:
    def __init__(self, user_id=None, username=None, password=None):
        self.id = user_id
        self.username = username
        self.password = password