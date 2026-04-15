# server/controllers/pano_controller.py

from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import io
import os
import piexif
import mimetypes
from PIL import Image
from datetime import datetime
import traceback
import logging

# Use centralized Database class
from database import Database
from storage import MinioStorage
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pano_blueprint = Blueprint("pano", __name__)

class PanoController:
    def __init__(self):
        # Use centralized Database class (connects via pgbouncer)
        self.db = Database()
        self.storage = MinioStorage()
        
        # Подтягиваем имя бакета из конфигурации (.env)
        self.pano_bucket = getattr(config, 'MINIO_BUCKET_NAME', 'panoramas')
        
        # Гарантируем, что таблица photos_4326 и индексы существуют!
        self._ensure_table()
        
        # Ensure bucket exists
        if self.storage.client:
            try:
                # Используем динамическое имя бакета
                if not self.storage.client.bucket_exists(self.pano_bucket):
                    self.storage.client.make_bucket(self.pano_bucket)
            except Exception as e:
                logger.warning(f"MinIO bucket warning: {e}")

    def _ensure_table(self):
        """Создает таблицу photos_4326 и необходимые индексы, если их нет"""
        try:
            cursor = self.db.get_cursor()
            
            # 1. Создаем таблицу (если нет)
            query_table = """
                CREATE TABLE IF NOT EXISTS public.photos_4326 (
                    id SERIAL PRIMARY KEY,
                    geom geometry(PointZ, 4326),
                    path VARCHAR,
                    filename VARCHAR,
                    directory VARCHAR,
                    altitude NUMERIC,
                    direction NUMERIC,
                    rotation INTEGER,
                    longitude VARCHAR,
                    latitude VARCHAR,
                    "timestamp" TIMESTAMP,
                    "order" INTEGER
                );
            """
            cursor.execute(query_table)

            # 2. Идемпотентное создание пространственного индекса
            query_gist_index = """
                CREATE INDEX IF NOT EXISTS idx_photos_4326_geom_gist 
                ON public.photos_4326 USING GIST (geom);
            """
            cursor.execute(query_gist_index)

            # 3. Опциональное создание обычного индекса по ID для быстрой сортировки
            query_id_index = """
                CREATE INDEX IF NOT EXISTS idx_photos_4326_id 
                ON public.photos_4326 (id DESC);
            """
            cursor.execute(query_id_index)

            self.db.commit()
            logger.info("Table photos_4326 and indexes are ready.")
        except Exception as e:
            logger.warning(f"Could not initialize photos_4326 or indexes: {e}")
            if self.db.connection:
                self.db.connection.rollback()

    @staticmethod
    def register_routes(blueprint):
        controller = PanoController()
        
        # List (with BBOX support)
        blueprint.add_url_rule("/panoramas", view_func=controller.get_panoramas, methods=["GET"])
        
        # Upload
        blueprint.add_url_rule("/upload", view_func=controller.upload_pano_files, methods=["POST", "OPTIONS"])
        
        # Info
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.get_pano_info, methods=["GET"])
        
        # Download / Image
        blueprint.add_url_rule("/pano_info/<int:pano_id>/download", view_func=controller.download_pano_file, methods=["GET"])
        blueprint.add_url_rule("/panoramas/<path:filename>", view_func=controller.get_pano_image_direct, methods=["GET"])
        
        # Delete / Update
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.delete_pano, methods=["DELETE"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.update_pano, methods=["PUT"])

    @cross_origin()
    def get_panoramas(self):
        """
        Returns list of panoramas. Supports BBOX filtering and Server-Side Clustering.
        """
        try:
            # 1. Filter params
            north = request.args.get('north', type=float)
            south = request.args.get('south', type=float)
            east = request.args.get('east', type=float)
            west = request.args.get('west', type=float)
            zoom = request.args.get('zoom', type=int)
            # Ставим высокий лимит, чтобы на максимальном зуме не обрезались точки
            limit = request.args.get('limit', type=int, default=50000)

            cursor = self.db.get_cursor()

            # 2. Определяем размер сетки для кластеризации в зависимости от зума
            grid_size = None
            if zoom is not None and zoom < 18:
                # 1 градус ~ 111 км
                grids = {
                    # Зум 0-10: Очень сильная кластеризация (Один кластер на город/регион)
                    0: 20.0, 1: 20.0, 2: 10.0, 3: 5.0, 4: 2.5, 5: 1.5,
                    6: 1.0, 7: 0.5, 8: 0.25, 9: 0.15, 10: 0.1,
                    
                    # Зум 11-17: Умеренная кластеризация (Несколько кластеров на улицу)
                    11: 0.05, 12: 0.02, 13: 0.01, 14: 0.005,
                    15: 0.002, 16: 0.001, 17: 0.0005
                }
                # Fallback для непредвиденных значений меньше 18
                grid_size = grids.get(zoom, 0.0005)

            # 3. Build Query
            if north is not None and south is not None:
                if grid_size:
                    # СЕРВЕРНАЯ КЛАСТЕРИЗАЦИЯ (Зум 0 - 17)
                    query = """
                        SELECT 
                            MIN(id) as id, 
                            AVG(ST_Y(geom)) AS latitude, 
                            AVG(ST_X(geom)) AS longitude, 
                            MIN(filename) as filename, 
                            NULL as directory,
                            NULL as "timestamp",
                            COUNT(*) as count
                        FROM public.photos_4326
                        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                        GROUP BY ST_SnapToGrid(geom, %s)
                        LIMIT %s
                    """
                    params = (west, south, east, north, grid_size, limit)
                else:
                    # ОТДАЧА СЫРЫХ ТОЧЕК (Зум 18 - 23: Кластеризации нет вообще)
                    query = """
                        SELECT 
                            id, 
                            NULLIF(latitude, '')::float AS latitude, 
                            NULLIF(longitude, '')::float AS longitude, 
                            filename, 
                            directory,
                            "timestamp",
                            1 as count
                        FROM public.photos_4326
                        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                        ORDER BY id DESC
                        LIMIT %s
                    """
                    params = (west, south, east, north, limit)
            else:
                # Default: latest N (без BBOX)
                query = """
                    SELECT 
                        id, 
                        NULLIF(latitude, '')::float AS latitude, 
                        NULLIF(longitude, '')::float AS longitude, 
                        filename, 
                        directory,
                        "timestamp",
                        1 as count
                    FROM public.photos_4326
                    ORDER BY id DESC
                    LIMIT %s
                """
                params = (limit,)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 3. Format JSON
            results = []
            for row in rows:
                if isinstance(row, dict):
                    res = row
                else:
                    res = {
                        "id": row[0],
                        "latitude": row[1],
                        "longitude": row[2],
                        "filename": row[3],
                        "directory": row[4],
                        "timestamp": row[5],
                        "count": row[6]
                    }
                
                ts = res.get("timestamp")
                results.append({
                    "id": res["id"],
                    "latitude": float(res["latitude"]) if res["latitude"] is not None else 0.0,
                    "longitude": float(res["longitude"]) if res["longitude"] is not None else 0.0,
                    "filename": res["filename"],
                    "directory": res["directory"],
                    "timestamp": ts.isoformat() if ts else None,
                    "count": res["count"]
                })

            return jsonify(results)

        except Exception as e:
            logger.error(f"Error getting panoramas: {e}")
            traceback.print_exc()
            # If DB error, rollback to reset transaction state
            if self.db.connection:
                self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_info(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            query = """
                SELECT id, latitude, longitude, altitude, direction, filename, directory, "timestamp"
                FROM public.photos_4326 
                WHERE id = %s
            """
            cursor.execute(query, (pano_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict): data = row
                else: 
                    data = {
                        "id": row[0], "latitude": row[1], "longitude": row[2], 
                        "altitude": row[3], "direction": row[4], 
                        "filename": row[5], "directory": row[6], "timestamp": row[7]
                    }
                
                result = {
                    "id": data["id"],
                    "latitude": float(data["latitude"]) if data["latitude"] else 0,
                    "longitude": float(data["longitude"]) if data["longitude"] else 0,
                    "altitude": float(data["altitude"]) if data["altitude"] else 0,
                    "direction": float(data["direction"]) if data["direction"] else 0,
                    "filename": data["filename"],
                    "directory": data["directory"],
                    "timestamp": data["timestamp"].isoformat() if data["timestamp"] else None
                }
                return jsonify(result)
            else:
                return jsonify({"error": "Not found"}), 404
        except Exception as e:
            if self.db.connection: self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def download_pano_file(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cursor.fetchone()
            
            if not res:
                return jsonify({"error": "Not found"}), 404

            filename = res['filename'] if isinstance(res, dict) else res[0]
            
            # Динамический MIME-тип на основе расширения файла
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Switch bucket context
            orig_bucket = self.storage.bucket_name
            self.storage.bucket_name = self.pano_bucket
            
            # Try MinIO
            response = None
            if self.storage.client:
                try:
                    response = self.storage.send_local_file(filename, mimetype=mime_type)
                except: pass
            
            self.storage.bucket_name = orig_bucket
            
            if response: return response
            return jsonify({"error": "File not found in storage"}), 404

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_image_direct(self, filename):
        try:
            # Динамический MIME-тип
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "application/octet-stream"

            orig_bucket = self.storage.bucket_name
            self.storage.bucket_name = self.pano_bucket
            response = self.storage.send_local_file(filename, mimetype=mime_type)
            self.storage.bucket_name = orig_bucket
            return response
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @cross_origin()
    def upload_pano_files(self):
        if request.method == "OPTIONS":
            return "", 200

        uploaded_files = request.files.getlist("files")
        successful = []
        failed = []
        failed_reasons = [] # Сюда складываем причины сбоя

        orig_bucket = self.storage.bucket_name
        self.storage.bucket_name = self.pano_bucket

        try:
            for file in uploaded_files:
                try:
                    original_name = file.filename
                    file_content = file.read()
                    
                    # Динамический тип для загрузки
                    mime_type, _ = mimetypes.guess_type(original_name)
                    if not mime_type:
                        mime_type = "image/jpeg"
                    
                    # 1. Parse EXIF
                    img_stream = io.BytesIO(file_content)
                    lat, lon, alt, direction, dt = self._parse_exif_data(img_stream)
                    
                    if lat is None or lon is None:
                        raise ValueError("В файле нет GPS-координат (EXIF)")

                    # 2. Filename
                    timestamp_str = dt.strftime("%Y%m%d_%H%M%S") if dt else "nodate"
                    new_filename = f"pano_{timestamp_str}_{original_name}"
                    
                    file_path = f"{self.pano_bucket}/{new_filename}" 

                    # 3. MinIO Upload (сохраняем с правильным типом WebP/JPEG)
                    save_stream = io.BytesIO(file_content)
                    self.storage.save_file(save_stream, new_filename, content_type=mime_type)

                    # 4. DB Insert
                    self._insert_pano_db(new_filename, file_path, lat, lon, alt, direction, dt)
                    
                    successful.append(original_name)
                    logger.info(f"Uploaded {original_name}")

                except Exception as e:
                    logger.error(f"Error uploading {file.filename}: {e}")
                    failed.append(file.filename)
                    failed_reasons.append(str(e))

            return jsonify({
                "message": "Upload complete",
                "successful_uploads": successful,
                "failed_uploads": failed,
                "skipped_files": failed_reasons # Отправляем точные причины!
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            self.storage.bucket_name = orig_bucket

    @cross_origin()
    def delete_pano(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cursor.fetchone()
            
            if res:
                filename = res['filename'] if isinstance(res, dict) else res[0]
                
                cursor.execute("DELETE FROM public.photos_4326 WHERE id = %s", (pano_id,))
                self.db.commit()
                
                orig = self.storage.bucket_name
                self.storage.bucket_name = self.pano_bucket
                self.storage.delete_file(filename)
                self.storage.bucket_name = orig
                
                return jsonify({"status": "deleted"})
            
            return jsonify({"error": "Not found"}), 404
        except Exception as e:
            if self.db.connection: self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def update_pano(self, pano_id):
        return jsonify({"status": "error", "message": "Update not implemented"}), 501

    # --- HELPERS ---

    def _insert_pano_db(self, filename, path, lat, lon, alt, direction, timestamp):
        cursor = self.db.get_cursor()
        query = """
            INSERT INTO public.photos_4326 (
                geom, path, filename, directory, 
                altitude, direction, rotation, 
                longitude, latitude, "timestamp", "order"
            ) VALUES (
                ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326),
                %s, %s, %s, 
                %s, %s, 0, 
                %s, %s, %s, 0
            )
        """
        values = (
            float(lon), float(lat), float(alt or 0),
            path, filename, self.pano_bucket,
            float(alt or 0), float(direction or 0),
            str(lon), str(lat), timestamp or datetime.now()
        )
        cursor.execute(query, values)
        self.db.commit()

    def _parse_exif_data(self, stream):
        try:
            img = Image.open(stream)
            exif = img.getexif()
            
            # Фоллбэк: если getexif пуст, пробуем вытащить старым добрым piexif
            if not exif and "exif" in img.info:
                try:
                    exif_dict = piexif.load(img.info["exif"])
                    gps = exif_dict.get("GPS", {})
                    lat = lon = alt = None
                    if piexif.GPSIFD.GPSLatitude in gps:
                        lat = self._convert_to_degrees(gps[piexif.GPSIFD.GPSLatitude])
                        if gps.get(piexif.GPSIFD.GPSLatitudeRef) == b'S': lat = -lat
                    if piexif.GPSIFD.GPSLongitude in gps:
                        lon = self._convert_to_degrees(gps[piexif.GPSIFD.GPSLongitude])
                        if gps.get(piexif.GPSIFD.GPSLongitudeRef) == b'W': lon = -lon
                    direction = 0.0
                    return lat, lon, alt, direction, None
                except: pass

            if not exif:
                return None, None, 0, 0, None
                
            # Читаем данные встроенным парсером Pillow (34853 - ID для GPS)
            gps_ifd = exif.get_ifd(34853) if hasattr(exif, 'get_ifd') else {}
            
            lat = lon = alt = None
            
            def safe_float(v):
                try: return float(v)
                except: return 0.0

            def convert_to_degrees(value):
                if not value or len(value) < 3: return 0.0
                return safe_float(value[0]) + (safe_float(value[1]) / 60.0) + (safe_float(value[2]) / 3600.0)

            if 2 in gps_ifd and 1 in gps_ifd:
                lat = convert_to_degrees(gps_ifd[2])
                if gps_ifd[1] == 'S': lat = -lat
                
            if 4 in gps_ifd and 3 in gps_ifd:
                lon = convert_to_degrees(gps_ifd[4])
                if gps_ifd[3] == 'W': lon = -lon
                
            if 6 in gps_ifd:
                alt = safe_float(gps_ifd[6])

            direction = safe_float(gps_ifd.get(17, 0.0))
            
            dt = None
            # 34665 - ID для общих Exif данных
            exif_ifd = exif.get_ifd(34665) if hasattr(exif, 'get_ifd') else {}
            date_str = exif_ifd.get(36867) or exif.get(306)
            if date_str:
                try:
                    if isinstance(date_str, bytes): date_str = date_str.decode()
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except: pass
                
            return lat, lon, alt, direction, dt
        except Exception as e:
            logger.warning(f"Exif parsing error: {e}")
            return None, None, 0, 0, None

    def _convert_to_degrees(self, value):
        try:
            return float(value[0][0])/float(value[0][1]) + (float(value[1][0])/float(value[1][1]) / 60.0) + (float(value[2][0])/float(value[2][1]) / 3600.0)
        except: return 0.0

PanoController.register_routes(pano_blueprint)