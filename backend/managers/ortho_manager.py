# ./backend/managers/ortho_manager.py

from models.ortho import Ortho

class OrthoManager:
    def __init__(self, db):
        self.db = db

    def get_all_orthos(self):
        cursor = self.db.get_cursor()
        query = "SELECT id, filename, bounds FROM ortholist"
        cursor.execute(query)
        rows = cursor.fetchall()
        orthos = []
        for row in rows:
            ortho = Ortho(
                ortho_id=row["id"],
                filename=row["filename"],
                bounds=row["bounds"]
            )
            orthos.append(ortho)
        return orthos

    def get_ortho_by_id(self, ortho_id):
        cursor = self.db.get_cursor()
        query = "SELECT id, filename, bounds FROM ortholist WHERE id = ?"
        cursor.execute(query, (ortho_id,))
        row = cursor.fetchone()
        if row:
            return Ortho(
                ortho_id=row["id"],
                filename=row["filename"],
                bounds=row["bounds"]
            )
        return None

    def insert_ortho(self, ortho):
        cursor = self.db.get_cursor()
        query = """
            INSERT INTO ortholist (filename, bounds)
            VALUES (?, ?)
        """
        cursor.execute(query, (ortho.filename, ortho.bounds))
        self.db.commit()
        return cursor.lastrowid

    def update_ortho(self, ortho_id, updated_fields):
        if not updated_fields:
            return
        cursor = self.db.get_cursor()

        set_clause = []
        values = []
        for field, value in updated_fields.items():
            set_clause.append(f"{field} = ?")
            values.append(value)

        set_clause_str = ", ".join(set_clause)
        query = f"UPDATE ortholist SET {set_clause_str} WHERE id = ?"
        values.append(ortho_id)
        cursor.execute(query, tuple(values))
        self.db.commit()

    def delete_ortho(self, ortho_id):
        cursor = self.db.get_cursor()
        query = "DELETE FROM ortholist WHERE id = ?"
        cursor.execute(query, (ortho_id,))
        self.db.commit()