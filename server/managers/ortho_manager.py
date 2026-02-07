# ./backend/managers/ortho_manager.py

from models.ortho import Ortho
import json

class OrthoManager:
    def __init__(self, db):
        self.db = db
        # Создаем таблицу при инициализации, если её нет
        self._ensure_table()

    def _ensure_table(self):
        # [FIX] Используем синтаксис PostgreSQL (SERIAL вместо AUTOINCREMENT)
        query = """
        CREATE TABLE IF NOT EXISTS orthophotos (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            bounds TEXT,
            url TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            cursor = self.db.get_cursor()
            cursor.execute(query)
            self.db.commit()
        except Exception as e:
            print(f"Error creating table orthophotos: {e}")
            # [FIX] Обязательный rollback при ошибке в Postgres
            if self.db.connection:
                self.db.connection.rollback()

    def get_all_orthos(self):
        try:
            cursor = self.db.get_cursor()
            query = "SELECT id, filename, bounds FROM orthophotos ORDER BY id DESC"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            orthos = []
            for row in rows:
                # Psycopg2 с RealDictCursor возвращает dict
                if isinstance(row, dict):
                    r_id = row["id"]
                    r_name = row["filename"]
                    r_bounds = row["bounds"]
                else:
                    # Fallback на случай другого курсора
                    r_id, r_name, r_bounds = row[0], row[1], row[2]

                ortho = Ortho(
                    filename=r_name,
                    bounds=r_bounds
                )
                ortho.id = r_id
                orthos.append(ortho)
                
            return orthos
        except Exception as e:
            if self.db.connection:
                self.db.connection.rollback()
            raise e

    def get_ortho_by_id(self, ortho_id):
        try:
            cursor = self.db.get_cursor()
            # [FIX] Используем %s для Postgres
            query = "SELECT id, filename, bounds FROM orthophotos WHERE id = %s"
            cursor.execute(query, (ortho_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    r_id = row["id"]
                    r_name = row["filename"]
                    r_bounds = row["bounds"]
                else:
                    r_id, r_name, r_bounds = row[0], row[1], row[2]

                ortho = Ortho(
                    filename=r_name,
                    bounds=r_bounds
                )
                ortho.id = r_id
                return ortho
            return None
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def insert_ortho(self, ortho):
        try:
            cursor = self.db.get_cursor()
            # [FIX] Используем %s вместо ? и RETURNING id (так работает Postgres)
            query = """
                INSERT INTO orthophotos (filename, bounds, url)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            url_val = getattr(ortho, 'url', None)
            
            cursor.execute(query, (ortho.filename, ortho.bounds, url_val))
            
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
                set_clause.append(f"{field} = %s") # [FIX] %s
                values.append(value)

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
            query = "DELETE FROM orthophotos WHERE id = %s" # [FIX] %s
            cursor.execute(query, (ortho_id,))
            self.db.commit()
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise