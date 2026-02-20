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
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            crs TEXT,
            is_visible BOOLEAN DEFAULT FALSE,
            is_cog BOOLEAN DEFAULT FALSE
        )
        """
        try:
            cursor.execute(query_create)
            self.db.commit()
        except Exception as e:
            print(f"Error creating table orthophotos: {e}")
            if self.db.connection:
                self.db.connection.rollback()

        # --- МИГРАЦИИ (Добавление колонок в существующую таблицу) ---

        # 2. CRS
        try:
            query_migrate_crs = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS crs TEXT;"
            cursor.execute(query_migrate_crs)
            self.db.commit()
        except Exception as e:
            print(f"Migration warning (adding crs column): {e}")
            if self.db.connection:
                self.db.connection.rollback()

        # 3. is_visible
        try:
            query_migrate_vis = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT FALSE;"
            cursor.execute(query_migrate_vis)
            self.db.commit()
        except Exception as e:
            print(f"Migration warning (adding is_visible column): {e}")
            if self.db.connection:
                self.db.connection.rollback()

        # 4. is_cog (Cloud Optimized GeoTIFF)
        try:
            query_migrate_cog = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS is_cog BOOLEAN DEFAULT FALSE;"
            cursor.execute(query_migrate_cog)
            self.db.commit()
        except Exception as e:
            print(f"Migration warning (adding is_cog column): {e}")
            if self.db.connection:
                self.db.connection.rollback()

        # 5. Geometry (PostGIS MultiPolygon)
        try:
            # Пытаемся добавить поле geometry. 
            # Требует установленного PostGIS (CREATE EXTENSION postgis;) в базе.
            query_migrate_geom = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS geometry geometry(MultiPolygon, 4326);"
            cursor.execute(query_migrate_geom)
            self.db.commit()
        except Exception as e:
            print(f"Migration warning (adding geometry column): {e}. Make sure PostGIS extension is enabled.")
            if self.db.connection:
                self.db.connection.rollback()

        # 6. Preview Filename
        try:
            query_migrate_preview = "ALTER TABLE orthophotos ADD COLUMN IF NOT EXISTS preview_filename TEXT;"
            cursor.execute(query_migrate_preview)
            self.db.commit()
        except Exception as e:
            print(f"Migration warning (adding preview_filename column): {e}")
            if self.db.connection:
                self.db.connection.rollback()

    def get_all_orthos(self):
        try:
            cursor = self.db.get_cursor()
            # [UPDATED] Вытаскиваем крайние точки из геометрии с помощью PostGIS функций
            query = """
                SELECT id, filename, bounds, url, crs, upload_date, is_visible, is_cog, preview_filename,
                       ST_XMin(geometry) as wgs_west,
                       ST_YMin(geometry) as wgs_south,
                       ST_XMax(geometry) as wgs_east,
                       ST_YMax(geometry) as wgs_north
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
                orthos.append(ortho)
                
            return orthos
        except Exception as e:
            if self.db.connection:
                self.db.connection.rollback()
            raise e

    def get_ortho_by_id(self, ortho_id):
        try:
            cursor = self.db.get_cursor()
            # [UPDATED] Вытаскиваем крайние точки из геометрии для конкретного файла
            query = """
                SELECT id, filename, bounds, url, crs, upload_date, is_visible, is_cog, preview_filename,
                       ST_XMin(geometry) as wgs_west,
                       ST_YMin(geometry) as wgs_south,
                       ST_XMax(geometry) as wgs_east,
                       ST_YMax(geometry) as wgs_north
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
                return ortho
            return None
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def insert_ortho(self, ortho):
        try:
            cursor = self.db.get_cursor()
            
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
                if field in ['filename', 'bounds', 'url', 'crs', 'is_visible', 'is_cog', 'preview_filename']:
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