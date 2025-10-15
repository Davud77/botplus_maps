# ./backend/managers/pano_manager.py

from models.pano import Pano

class PanoManager:
    def __init__(self, db):
        self.db = db

    def create_pano(self, pano):
        cursor = self.db.get_cursor()
        query = """
            INSERT INTO panolist (
                filename, latitude, longitude, user_id, file_type, file_size,
                full_pano_width_pixels, full_pano_height_pixels, first_photo_date,
                model, altitude, focal_length, tags, upload_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """
        values = (
            pano.filename,
            pano.latitude,
            pano.longitude,
            pano.user_id,
            pano.file_type,
            pano.file_size,
            pano.width,
            pano.height,
            pano.first_photo_date.isoformat(' ') if pano.first_photo_date else None,
            pano.model,
            pano.altitude,
            pano.focal_length,
            pano.tags
        )
        cursor.execute(query, values)
        self.db.commit()
        return cursor.lastrowid

    def get_pano_list(self):
        cursor = self.db.get_cursor()
        query = "SELECT id, latitude, longitude FROM panolist"
        cursor.execute(query)
        rows = cursor.fetchall()
        return rows

    def get_pano_by_id(self, pano_id):
        cursor = self.db.get_cursor()
        query = "SELECT * FROM panolist WHERE id = ?"
        cursor.execute(query, (pano_id,))
        row = cursor.fetchone()
        return row

    def update_pano(self, pano_id, updated_fields):
        """
        Обновляет указанные поля в записи панорамы (pano_id).
        updated_fields - dict, ключи соответствуют названиям колонок в БД.
        """
        if not updated_fields:
            return None
        cursor = self.db.get_cursor()

        set_clause = []
        values = []
        for field, value in updated_fields.items():
            set_clause.append(f"{field} = ?")
            values.append(value)

        set_clause_str = ", ".join(set_clause)
        query = f"UPDATE panolist SET {set_clause_str} WHERE id = ?"
        values.append(pano_id)

        cursor.execute(query, tuple(values))
        self.db.commit()

    def delete_pano(self, pano_id):
        cursor = self.db.get_cursor()
        query = "DELETE FROM panolist WHERE id = ?"
        cursor.execute(query, (pano_id,))
        self.db.commit()