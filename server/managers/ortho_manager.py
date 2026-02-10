# ./backend/managers/ortho_manager.py

from models.ortho import Ortho
import json

class OrthoManager:
    def __init__(self, db):
        self.db = db
        # Создаем таблицу и проверяем структуру при инициализации
        self._ensure_table()

    def _ensure_table(self):
        cursor = self.db.get_cursor()
        
        # 1. Создание таблицы (если нет)
        query_create = """
        CREATE TABLE IF NOT EXISTS orthophotos (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            bounds TEXT,
            url TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            cursor.execute(query_create)
            self.db.commit()
        except Exception as e:
            print(f"Error creating table orthophotos: {e}")
            if self.db.connection:
                self.db.connection.rollback()

        # 2. МИГРАЦИЯ: Добавляем колонку CRS, если её нет
        # Это предотвращает ошибку 'column "crs" does not exist' на старых базах
        try:
            query_migrate = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS crs TEXT;"
            cursor.execute(query_migrate)
            self.db.commit()
        except Exception as e:
            # Игнорируем ошибку, если колонка уже есть или что-то пошло не так (но логируем)
            print(f"Migration warning (adding crs column): {e}")
            if self.db.connection:
                self.db.connection.rollback()

    def get_all_orthos(self):
        try:
            cursor = self.db.get_cursor()
            # [UPDATED] Добавляем crs в выборку
            query = "SELECT id, filename, bounds, url, crs, upload_date FROM orthophotos ORDER BY id DESC"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            orthos = []
            for row in rows:
                # Обработка разных типов курсоров (dict vs tuple)
                if isinstance(row, dict):
                    r_id = row["id"]
                    r_name = row["filename"]
                    r_bounds = row["bounds"]
                    r_url = row["url"]
                    r_crs = row.get("crs")
                    r_date = row["upload_date"]
                else:
                    r_id = row[0]
                    r_name = row[1]
                    r_bounds = row[2]
                    r_url = row[3]
                    r_crs = row[4] if len(row) > 4 else None
                    r_date = row[5] if len(row) > 5 else None

                ortho = Ortho(
                    filename=r_name,
                    bounds=r_bounds,
                    url=r_url,
                    ortho_id=r_id,
                    upload_date=r_date
                )
                # Динамически добавляем атрибут crs, так как он может не быть в __init__ модели
                ortho.crs = r_crs
                orthos.append(ortho)
                
            return orthos
        except Exception as e:
            if self.db.connection:
                self.db.connection.rollback()
            raise e

    def get_ortho_by_id(self, ortho_id):
        try:
            cursor = self.db.get_cursor()
            # [UPDATED] Добавляем crs в выборку
            query = "SELECT id, filename, bounds, url, crs, upload_date FROM orthophotos WHERE id = %s"
            cursor.execute(query, (ortho_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    r_id = row["id"]
                    r_name = row["filename"]
                    r_bounds = row["bounds"]
                    r_url = row["url"]
                    r_crs = row.get("crs")
                    r_date = row["upload_date"]
                else:
                    r_id = row[0]
                    r_name = row[1]
                    r_bounds = row[2]
                    r_url = row[3]
                    r_crs = row[4] if len(row) > 4 else None
                    r_date = row[5] if len(row) > 5 else None

                ortho = Ortho(
                    filename=r_name,
                    bounds=r_bounds,
                    url=r_url,
                    ortho_id=r_id,
                    upload_date=r_date
                )
                ortho.crs = r_crs
                return ortho
            return None
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def insert_ortho(self, ortho):
        try:
            cursor = self.db.get_cursor()
            
            # [UPDATED] Добавляем сохранение CRS
            # Используем безопасное получение атрибута, если модель еще не обновлена
            crs_val = getattr(ortho, 'crs', None)
            url_val = getattr(ortho, 'url', None)

            query = """
                INSERT INTO orthophotos (filename, bounds, url, crs)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            
            cursor.execute(query, (ortho.filename, ortho.bounds, url_val, crs_val))
            
            # Получаем ID новой записи
            row = cursor.fetchone()
            if isinstance(row, dict):
                new_id = row['id']
            else:
                new_id = row[0]
                
            self.db.commit()
            return new_id
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def update_ortho(self, ortho_id, updated_fields):
        if not updated_fields:
            return
        
        try:
            cursor = self.db.get_cursor()

            set_clause = []
            values = []
            for field, value in updated_fields.items():
                # Простая защита от SQL инъекций через имена полей (хотя тут ожидаются ключи из кода)
                # Разрешаем обновлять только известные поля
                if field in ['filename', 'bounds', 'url', 'crs']:
                    set_clause.append(f"{field} = %s")
                    values.append(value)

            if not set_clause:
                return

            set_clause_str = ", ".join(set_clause)
            query = f"UPDATE orthophotos SET {set_clause_str} WHERE id = %s"
            values.append(ortho_id)
            
            cursor.execute(query, tuple(values))
            self.db.commit()
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def delete_ortho(self, ortho_id):
        try:
            cursor = self.db.get_cursor()
            query = "DELETE FROM orthophotos WHERE id = %s"
            cursor.execute(query, (ortho_id,))
            self.db.commit()
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise