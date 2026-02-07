# ./backend/database.py

import psycopg2
from psycopg2.extras import RealDictCursor
import config
import os

class Database:
    """
    Класс-обёртка для работы с PostgreSQL.
    Настройки подключения берутся строго из config.py.
    """
    def __init__(self):
        # Используем переменные из config.py, которые мы только что настроили
        self.host = config.DB_HOST
        self.port = config.DB_PORT
        self.database = config.DB_NAME
        self.user = config.DB_USER
        self.password = config.DB_PASSWORD
        
        self.connection = None

    def connect(self):
        """
        Устанавливает соединение, если оно отсутствует или закрыто.
        """
        # Если объект соединения есть, но связь разорвана (closed != 0) — сбрасываем
        if self.connection is not None:
            if self.connection.closed != 0:
                self.connection = None

        if self.connection is None:
            try:
                self.connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    cursor_factory=RealDictCursor
                )
                # Автокоммит отключен, чтобы мы могли управлять транзакциями вручную (self.commit())
                self.connection.autocommit = False
            except Exception as e:
                # Логируем точные параметры подключения при ошибке
                print(f"CRITICAL: Failed to connect to PostgreSQL at {self.host}:{self.port}/{self.database}")
                print(f"Error details: {e}")
                raise e

    def get_cursor(self):
        """
        Возвращает курсор для выполнения запросов.
        """
        self.connect()
        return self.connection.cursor()

    def commit(self):
        """
        Фиксирует транзакцию.
        """
        if self.connection:
            self.connection.commit()

    def close(self):
        """
        Закрывает соединение.
        """
        if self.connection:
            self.connection.close()
            self.connection = None