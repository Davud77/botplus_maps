# ./backend/managers/ortho_manager.py

try:
    from ..models.ortho import Ortho
except ImportError:
    from models.ortho import Ortho
import json

class OrthoManager:
    def __init__(self, db, *, ensure_schema=True):
        self.db = db
        # Создаем таблицу и проверяем структуру при инициализации
        if ensure_schema:
            self._ensure_table()

    def _ensure_table(self):
        # Transitional legacy initialization. Replace with versioned migrations in M1.
        with self.db.cursor(write=True) as cursor:
            # Serialize transitional startup DDL across Gunicorn workers.
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (self.db.LEGACY_SCHEMA_LOCK,))
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orthophotos (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    bounds TEXT,
                    url TEXT,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    crs TEXT,
                    is_visible BOOLEAN DEFAULT FALSE,
                    is_cog BOOLEAN DEFAULT FALSE
                )
            """)
            for statement in (
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS crs TEXT",
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT FALSE",
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS is_cog BOOLEAN DEFAULT FALSE",
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS geometry geometry(MultiPolygon, 4326)",
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS preview_filename TEXT",
                "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS display_name VARCHAR(240)",
            ):
                cursor.execute(statement)

    def get_all_orthos(self):
        with self.db.cursor(write=False) as cursor:
            # [UPDATED] Вытаскиваем крайние точки из геометрии с помощью PostGIS функций
            query = """
                SELECT id, filename, bounds, url, crs, upload_date, is_visible, is_cog, preview_filename,
                       ST_XMin(geometry) as wgs_west,
                       ST_YMin(geometry) as wgs_south,
                       ST_XMax(geometry) as wgs_east,
                       ST_YMax(geometry) as wgs_north, display_name
                FROM orthophotos ORDER BY id DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

        orthos = []
        for row in rows:
            if isinstance(row, dict):
                r_id = row["id"]
                r_name = row["filename"]
                r_bounds = row["bounds"]
                r_url = row["url"]
                r_crs = row.get("crs")
                r_date = row["upload_date"]
                r_vis = row.get("is_visible", False)
                r_cog = row.get("is_cog", False)
                r_preview = row.get("preview_filename")
                w_west = row.get("wgs_west")
                w_south = row.get("wgs_south")
                w_east = row.get("wgs_east")
                w_north = row.get("wgs_north")
            else:
                r_id = row[0]
                r_name = row[1]
                r_bounds = row[2]
                r_url = row[3]
                r_crs = row[4] if len(row) > 4 else None
                r_date = row[5] if len(row) > 5 else None
                r_vis = row[6] if len(row) > 6 else False
                r_cog = row[7] if len(row) > 7 else False
                r_preview = row[8] if len(row) > 8 else None
                w_west = row[9] if len(row) > 9 else None
                w_south = row[10] if len(row) > 10 else None
                w_east = row[11] if len(row) > 11 else None
                w_north = row[12] if len(row) > 12 else None

            # [NEW] Формируем объект WGS84 границ, если геометрия существует
            wgs84_bounds = None
            if w_west is not None and w_south is not None:
                wgs84_bounds = { "west": w_west, "south": w_south, "east": w_east, "north": w_north }

            ortho = Ortho(
                filename=r_name,
                bounds=r_bounds,
                url=r_url,
                ortho_id=r_id,
                upload_date=r_date,
                crs=r_crs,
                is_visible=r_vis,
                is_cog=r_cog,
                preview_filename=r_preview,
                wgs84_bounds=wgs84_bounds # Передаем в модель
            )
            ortho.display_name = row.get("display_name") if isinstance(row,dict) else row[13]
            orthos.append(ortho)

        return orthos

    def get_ortho_by_id(self, ortho_id):
        with self.db.cursor(write=False) as cursor:
            # [UPDATED] Вытаскиваем крайние точки из геометрии для конкретного файла
            query = """
                SELECT id, filename, bounds, url, crs, upload_date, is_visible, is_cog, preview_filename,
                       ST_XMin(geometry) as wgs_west,
                       ST_YMin(geometry) as wgs_south,
                       ST_XMax(geometry) as wgs_east,
                       ST_YMax(geometry) as wgs_north, display_name
                FROM orthophotos WHERE id = %s
            """
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
                r_vis = row.get("is_visible", False)
                r_cog = row.get("is_cog", False)
                r_preview = row.get("preview_filename")
                w_west = row.get("wgs_west")
                w_south = row.get("wgs_south")
                w_east = row.get("wgs_east")
                w_north = row.get("wgs_north")
            else:
                r_id = row[0]
                r_name = row[1]
                r_bounds = row[2]
                r_url = row[3]
                r_crs = row[4] if len(row) > 4 else None
                r_date = row[5] if len(row) > 5 else None
                r_vis = row[6] if len(row) > 6 else False
                r_cog = row[7] if len(row) > 7 else False
                r_preview = row[8] if len(row) > 8 else None
                w_west = row[9] if len(row) > 9 else None
                w_south = row[10] if len(row) > 10 else None
                w_east = row[11] if len(row) > 11 else None
                w_north = row[12] if len(row) > 12 else None

            # [NEW] Формируем объект WGS84 границ
            wgs84_bounds = None
            if w_west is not None and w_south is not None:
                wgs84_bounds = { "west": w_west, "south": w_south, "east": w_east, "north": w_north }

            ortho = Ortho(
                filename=r_name,
                bounds=r_bounds,
                url=r_url,
                ortho_id=r_id,
                upload_date=r_date,
                crs=r_crs,
                is_visible=r_vis,
                is_cog=r_cog,
                preview_filename=r_preview,
                wgs84_bounds=wgs84_bounds # Передаем в модель
            )
            ortho.display_name = row.get("display_name") if isinstance(row,dict) else row[13]
            return ortho
        return None

    def insert_ortho(self, ortho):
        with self.db.cursor(write=True) as cursor:

            crs_val = getattr(ortho, 'crs', None)
            url_val = getattr(ortho, 'url', None)
            vis_val = getattr(ortho, 'is_visible', False)
            cog_val = getattr(ortho, 'is_cog', False)
            geom_wkt = getattr(ortho, 'geometry_wkt', None)
            preview_val = getattr(ortho, 'preview_filename', None)

            # Если передана геометрия (WKT), используем PostGIS функцию ST_Multi(ST_GeomFromText(..., 4326))
            if geom_wkt:
                query = """
                    INSERT INTO orthophotos (filename, bounds, url, crs, is_visible, is_cog, preview_filename, geometry)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, ST_Multi(ST_GeomFromText(%s, 4326)))
                    RETURNING id
                """
                cursor.execute(query, (ortho.filename, ortho.bounds, url_val, crs_val, vis_val, cog_val, preview_val, geom_wkt))
            else:
                query = """
                    INSERT INTO orthophotos (filename, bounds, url, crs, is_visible, is_cog, preview_filename)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                cursor.execute(query, (ortho.filename, ortho.bounds, url_val, crs_val, vis_val, cog_val, preview_val))

            row = cursor.fetchone()
            if isinstance(row, dict):
                new_id = row['id']
            else:
                new_id = row[0]

            return new_id

    def update_ortho(self, ortho_id, updated_fields):
        if not updated_fields:
            return

        with self.db.cursor(write=True) as cursor:

            set_clause = []
            values = []
            for field, value in updated_fields.items():
                if field in ['display_name', 'filename', 'bounds', 'url', 'crs', 'is_visible', 'is_cog', 'preview_filename']:
                    set_clause.append(f"{field} = %s")
                    values.append(value)

            if not set_clause:
                return

            set_clause_str = ", ".join(set_clause)
            query = f"UPDATE orthophotos SET {set_clause_str} WHERE id = %s"
            values.append(ortho_id)

            cursor.execute(query, tuple(values))

    def delete_ortho(self, ortho_id):
        with self.db.cursor(write=True) as cursor:
            query = "DELETE FROM orthophotos WHERE id = %s"
            cursor.execute(query, (ortho_id,))
