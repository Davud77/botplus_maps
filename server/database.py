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
        # Используем готовую строку подключения DATABASE_URL из config (приоритетный способ), 
        # либо собираем из отдельных переменных, если её нет.
        self.database_url = getattr(config, "DATABASE_URL", None)
        
        # Оставляем отдельные переменные для обратной совместимости 
        # и детального логирования при ошибках
        self.host = getattr(config, "DB_HOST", "pgbouncer")
        self.port = getattr(config, "DB_PORT", "6432")
        self.database = getattr(config, "DB_NAME", "botplus_db")
        self.user = getattr(config, "DB_USER", "botplus_user")
        self.password = getattr(config, "DB_PASSWORD", "botplus_password")
        
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
                if self.database_url:
                    # Подключение через единый URL (идеально для PgBouncer и SQLAlchemy)
                    self.connection = psycopg2.connect(
                        self.database_url,
                        cursor_factory=RealDictCursor
                    )
                else:
                    # Fallback на классический метод передачи аргументов
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

    def rollback(self):
        """
        Откатывает транзакцию (полезно при обработке исключений).
        """
        if self.connection:
            self.connection.rollback()

    def close(self):
        """
        Закрывает соединение.
        """
        if self.connection:
            self.connection.close()
            self.connection = None