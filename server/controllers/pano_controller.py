# server/controllers/pano_controller.py

from flask import Blueprint, request, jsonify, send_file, Response
from flask_cors import cross_origin
import os
import piexif
import mimetypes
from PIL import Image
from pathlib import Path
import uuid
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from datetime import datetime
import traceback
import logging
import json
from services.media_metadata import read_media_metadata, display_name

# Use centralized Database class
try:
    from ..database import Database
    from ..storage import FileStorage
    from .. import config
except ImportError:
    from database import Database
    from storage import FileStorage
    import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PanoController:
    def __init__(self):
        # Use centralized Database class (connects via pgbouncer)
        self.db = Database()
        self.storage = FileStorage(Path(config.MEDIA_ROOT) / 'panoramas')
        self._ensure_table()

    def _ensure_table(self):
        """Создает таблицу photos_4326 и необходимые индексы, если их нет"""
        with self.db.cursor(write=True) as cursor:
            # Serialize transitional startup DDL across Gunicorn workers.
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (self.db.LEGACY_SCHEMA_LOCK,))

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

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_4326_filename ON public.photos_4326 (filename)")

            logger.info("Table photos_4326 and indexes are ready.")

    @staticmethod
    def register_routes(blueprint, controller=None):
        controller = controller if controller is not None else PanoController()

        blueprint.add_url_rule("/panoramas", view_func=controller.get_panoramas, methods=["GET"])
        blueprint.add_url_rule("/upload", view_func=controller.upload_pano_files, methods=["POST", "OPTIONS"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.get_pano_info, methods=["GET"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>/download", view_func=controller.download_pano_file, methods=["GET"])
        blueprint.add_url_rule("/panoramas/<path:filename>", view_func=controller.get_pano_image_direct, methods=["GET"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.delete_pano, methods=["DELETE"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.update_pano, methods=["PUT"])

    @cross_origin()
    def get_panoramas(self):
        """
        Сверхбыстрая отдача панорам. Формирование JSON происходит прямо в PostgreSQL (C-level).
        """
        try:
            north = request.args.get('north', type=float)
            south = request.args.get('south', type=float)
            east = request.args.get('east', type=float)
            west = request.args.get('west', type=float)
            zoom = request.args.get('zoom', type=int)
            limit = request.args.get('limit', type=int, default=50000)

            grid_size = None

            # Строгая логика зумов:
            if zoom is not None and zoom <= 17:
                grids = {
                    # Зум 0-10: Очень сильная кластеризация (~2000 км -> ~11 км). 1 кластер на город/регион.
                    0: 20.0, 1: 10.0, 2: 5.0, 3: 2.5, 4: 1.5,
                    5: 1.0, 6: 0.8, 7: 0.6, 8: 0.4, 9: 0.2, 10: 0.1,

                    # Зум 11-17: Умеренная кластеризация (~5 км -> ~50 метров). Несколько на улицу.
                    11: 0.05, 12: 0.025, 13: 0.012, 14: 0.006,
                    15: 0.003, 16: 0.0015, 17: 0.0005
                }
                grid_size = grids.get(zoom, 0.0005)

            if north is not None and south is not None:
                if grid_size:
                    # PostgreSQL сам группирует и собирает JSON массив
                    query = """
                        SELECT COALESCE(json_agg(json_build_object(
                            'id', sub.id,
                            'lat', sub.lat,
                            'lng', sub.lng,
                            'count', sub.count
                        )), '[]'::json)
                        FROM (
                            SELECT
                                MIN(id) as id,
                                ROUND(AVG(ST_Y(geom))::numeric, 6) AS lat,
                                ROUND(AVG(ST_X(geom))::numeric, 6) AS lng,
                                COUNT(*) as count
                            FROM public.photos_4326
                            WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                            GROUP BY ST_SnapToGrid(geom, %s)
                            LIMIT %s
                        ) sub;
                    """
                    params = (west, south, east, north, grid_size, limit)
                else:
                    # Сырые точки (Зум 18+)
                    query = """
                        SELECT COALESCE(json_agg(json_build_object(
                            'id', sub.id,
                            'lat', sub.lat,
                            'lng', sub.lng,
                            'count', 1
                        )), '[]'::json)
                        FROM (
                            SELECT
                                id,
                                ROUND(ST_Y(geom)::numeric, 6) as lat,
                                ROUND(ST_X(geom)::numeric, 6) as lng
                            FROM public.photos_4326
                            WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                            ORDER BY id DESC
                            LIMIT %s
                        ) sub;
                    """
                    params = (west, south, east, north, limit)
            else:
                # Дефолтный ответ без BBOX
                query = """
                    SELECT COALESCE(json_agg(json_build_object(
                        'id', id,
                        'lat', ROUND(ST_Y(geom)::numeric, 6),
                        'lng', ROUND(ST_X(geom)::numeric, 6),
                        'count', 1
                    )), '[]'::json)
                    FROM (
                        SELECT id, geom FROM public.photos_4326 ORDER BY id DESC LIMIT %s
                    ) sub;
                """
                params = (limit,)

            with self.db.cursor(dict_rows=False) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()[0]

            # Возвращаем напрямую
            if isinstance(result, str):
                return Response(result, mimetype='application/json')
            elif isinstance(result, dict) or isinstance(result, list):
                return jsonify(result)
            else:
                return Response(json.dumps(result), mimetype='application/json')

        except Exception as e:
            logger.error(f"Error getting panoramas: {e}")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_info(self, pano_id):
        try:
            query = 'SELECT id, latitude, longitude, altitude, direction, filename, directory, "timestamp" FROM public.photos_4326 WHERE id = %s'
            with self.db.cursor() as cursor:
                cursor.execute(query, (pano_id,))
                row = cursor.fetchone()
            if row:
                data = row if isinstance(row, dict) else {"id": row[0], "latitude": row[1], "longitude": row[2], "altitude": row[3], "direction": row[4], "filename": row[5], "directory": row[6], "timestamp": row[7]}
                try:
                    metadata = read_media_metadata(self.storage.get_local_file_path(data['filename']))
                except OSError:
                    metadata = {}
                return jsonify({
                    **metadata, "display_name": display_name(data["filename"]),
                    "id": data["id"], "latitude": float(data["latitude"]) if data["latitude"] else 0, "longitude": float(data["longitude"]) if data["longitude"] else 0,
                    "altitude": float(data["altitude"]) if data["altitude"] else 0, "direction": float(data["direction"]) if data["direction"] else 0,
                    "filename": data["filename"], "directory": data["directory"], "timestamp": data["timestamp"].isoformat() if data["timestamp"] else None
                })
            return jsonify({"error": "Not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def download_pano_file(self, pano_id):
        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
                res = cursor.fetchone()
            if not res: return jsonify({"error": "Not found"}), 404
            filename = res['filename'] if isinstance(res, dict) else res[0]
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type: mime_type = "application/octet-stream"
            return self.storage.send_local_file(filename, mimetype=mime_type, as_attachment=True)
        except HTTPException:
            raise
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_image_direct(self, filename):
        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT 1 FROM public.photos_4326 WHERE filename=%s LIMIT 1", (filename,))
                if not cursor.fetchone():
                    return jsonify({"error": "Not found"}), 404
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type: mime_type = "application/octet-stream"
            return self.storage.send_local_file(filename, mimetype=mime_type)
        except HTTPException:
            raise
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @cross_origin()
    def upload_pano_files(self):
        if request.method == "OPTIONS": return "", 200
        uploaded_files = request.files.getlist("files")
        successful, failed, failed_reasons = [], [], []
        for file in uploaded_files:
            new_filename = None
            saved = False
            try:
                original_name = file.filename or ''
                mime_type = mimetypes.guess_type(original_name)[0] or 'image/jpeg'
                # Parse EXIF on Werkzeug's seekable spooled stream, not a full read.
                lat, lon, alt, direction, dt = self._parse_exif_data(file.stream)
                if lat is None or lon is None:
                    raise ValueError("В файле нет GPS-координат (EXIF)")
                identifier = uuid.uuid4().hex
                safe_name = secure_filename(original_name.replace('\\', '/').rsplit('/', 1)[-1])[:160] or 'panorama.jpg'
                new_filename = f"{identifier[:2]}/{identifier[2:4]}/{identifier}_{safe_name}"
                file.stream.seek(0)
                self.storage.save_file(file.stream, new_filename, content_type=mime_type)
                saved = True
                self._insert_pano_db(new_filename, f"panoramas/{new_filename}", lat, lon, alt, direction, dt)
                successful.append(original_name)
            except Exception as error:
                if saved:
                    try:
                        self.storage.delete_file(new_filename)
                    except OSError:
                        logger.exception('Could not clean up unregistered panorama')
                failed.append(file.filename)
                failed_reasons.append(str(error))
        return jsonify({"message": "Upload complete", "successful_uploads": successful,
                        "failed_uploads": failed, "skipped_files": failed_reasons})

    @cross_origin()
    def delete_pano(self, pano_id):
        try:
            with self.db.cursor(write=True) as cursor:
                cursor.execute("DELETE FROM public.photos_4326 WHERE id = %s RETURNING filename", (pano_id,))
                res = cursor.fetchone()
            if not res:
                return jsonify({"error": "Not found"}), 404
            # File I/O happens after the DB transaction is released.
            self.storage.delete_file(res["filename"])
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def update_pano(self, pano_id):
        return jsonify({"status": "error", "message": "Update not implemented"}), 501

    def _insert_pano_db(self, filename, path, lat, lon, alt, direction, timestamp):
        query = 'INSERT INTO public.photos_4326 (geom, path, filename, directory, altitude, direction, rotation, longitude, latitude, "timestamp", "order") VALUES (ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326), %s, %s, %s, %s, %s, 0, %s, %s, %s, 0)'
        values = (float(lon), float(lat), float(alt or 0), path, filename, 'panoramas', float(alt or 0), float(direction or 0), str(lon), str(lat), timestamp or datetime.now())
        with self.db.cursor(write=True) as cursor:
            cursor.execute(query, values)

    def _parse_exif_data(self, stream):
        try:
            img = Image.open(stream)
            exif = img.getexif()
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
            if not exif: return None, None, 0, 0, None
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
            if 6 in gps_ifd: alt = safe_float(gps_ifd[6])
            direction = safe_float(gps_ifd.get(17, 0.0))
            dt = None
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
        try: return float(value[0][0])/float(value[0][1]) + (float(value[1][0])/float(value[1][1]) / 60.0) + (float(value[2][0])/float(value[2][1]) / 3600.0)
        except: return 0.0

def create_pano_blueprint(controller=None):
    blueprint = Blueprint("pano", __name__)
    PanoController.register_routes(blueprint, controller)
    return blueprint
