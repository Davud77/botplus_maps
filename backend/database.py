# ./backend/database.py

import sqlite3
import config

class Database:
    """
    Класс-обёртка для работы с SQLite.
    """
    def __init__(self):
        self.db_file = config.DB_FILE
        self.connection = None

    def connect(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Результаты в виде словарей

    def get_cursor(self):
        self.connect()
        return self.connection.cursor()

    def commit(self):
        if self.connection:
            self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None