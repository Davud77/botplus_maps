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
from services.media_metadata import read_media_metadata, display_name, media_kind

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

            try:
                from .media_catalog import initialize
            except ImportError:
                from controllers.media_catalog import initialize
            initialize(cursor)
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
        from services.panorama_index import markers
        return markers(self.db,allow_world=True)

    def source_file(self, row):
        source=row.get('source_ref') if isinstance(row,dict) else None
        if source:
            import import_jobs
            from media_worker import source_path
            root,path=source_path(source['root_id'],source['key'])
            if import_jobs.fingerprint(path)!=source['fingerprint']:
                from flask import abort
                abort(409,description='Исходник изменён. Выполните импорт повторно.')
            return str(path)
        return self.storage.get_local_file_path(row['filename'])

    @cross_origin()
    def get_pano_info(self, pano_id):
        try:
            query = 'SELECT id, latitude, longitude, altitude, direction, filename, directory, "timestamp", source_ref FROM public.photos_4326 WHERE id = %s AND deleted_at IS NULL'
            with self.db.cursor() as cursor:
                cursor.execute(query, (pano_id,))
                row = cursor.fetchone()
            if row:
                data = row if isinstance(row, dict) else {"id": row[0], "latitude": row[1], "longitude": row[2], "altitude": row[3], "direction": row[4], "filename": row[5], "directory": row[6], "timestamp": row[7]}
                try:
                    metadata = read_media_metadata(self.source_file(data))
                except OSError:
                    metadata = {}
                return jsonify({
                    **metadata, "display_name": display_name(data["filename"]),
                    "id": data["id"], "latitude": float(data["latitude"]) if data["latitude"] else 0, "longitude": float(data["longitude"]) if data["longitude"] else 0,
                    "altitude": float(data["altitude"]) if data["altitude"] else 0, "direction": float(data["direction"]) if data["direction"] else 0,
                    "filename": data["filename"], "directory": data["directory"], "timestamp": data["timestamp"].isoformat() if data["timestamp"] else None
                })
            return jsonify({"error": "Not found"}), 404
        except HTTPException:
            raise
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def download_pano_file(self, pano_id):
        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT filename,source_ref FROM public.photos_4326 WHERE id = %s AND deleted_at IS NULL", (pano_id,))
                res = cursor.fetchone()
            if not res: return jsonify({"error": "Not found"}), 404
            filename = res['filename'] if isinstance(res, dict) else res[0]
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type: mime_type = "application/octet-stream"
            if res.get('source_ref'):
                return send_file(self.source_file(res),mimetype=mime_type,as_attachment=True,download_name=display_name(filename))
            return self.storage.send_local_file(filename, mimetype=mime_type, as_attachment=True)
        except HTTPException:
            raise
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_image_direct(self, filename):
        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT filename,source_ref FROM public.photos_4326 WHERE filename=%s AND deleted_at IS NULL LIMIT 1", (filename,))
                row=cursor.fetchone()
                if not row:
                    return jsonify({"error": "Not found"}), 404
            if row.get('source_ref'):
                return send_file(self.source_file(row),mimetype=mimetypes.guess_type(filename)[0] or 'image/jpeg')
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
        request.max_content_length = 128*1024*1024
        uploaded_files = request.files.getlist("files")
        successful, failed, failed_reasons = [], [], []
        for file in uploaded_files:
            new_filename = None
            saved = False
            try:
                original_name = file.filename or ''
                mime_type = mimetypes.guess_type(original_name)[0] or 'image/jpeg'
                if Path(original_name).suffix.lower() not in {'.jpg','.jpeg','.webp'}: raise ValueError('Поддерживаются JPEG и WebP.')
                from flask import g
                from psycopg2.extras import Json
                tags=request.form.get('tags','')
                if len(tags)>2000:raise ValueError('Теги: не более 2000 символов.')
                new_filename=uuid.uuid4().hex+Path(original_name).suffix.lower()
                staging=FileStorage(Path(config.MEDIA_ROOT)/'panoramas'/'incoming')
                staging.save_file(file.stream,new_filename)
                saved=True
                with self.db.cursor(write=True) as cur:
                    cur.execute('INSERT INTO media_import_jobs(id,owner_id,source) VALUES (%s,%s,%s)',
                        (str(uuid.uuid4()),g.current_user_id,Json({'root_id':'__media_uploads','key':new_filename,
                            'title':original_name,'only_360':request.form.get('only_360')=='true','tags':tags})))
                successful.append(original_name)
            except Exception as error:
                if saved:
                    try:
                        staging.delete_file(new_filename)
                    except OSError:
                        logger.exception('Could not clean up unregistered panorama')
                failed.append(file.filename)
                failed_reasons.append(str(error))
        return jsonify({"message": "Queued for background import", "successful_uploads": successful,
                        "failed_uploads": failed, "skipped_files": failed_reasons})

    @cross_origin()
    def delete_pano(self, pano_id):
        try:
            with self.db.cursor(write=True) as cursor:
                cursor.execute("DELETE FROM public.photos_4326 WHERE id = %s RETURNING filename,source_ref", (pano_id,))
                res = cursor.fetchone()
            if not res:
                return jsonify({"error": "Not found"}), 404
            # File I/O happens after the DB transaction is released.
            source=res.get('source_ref')
            if source and source.get('root_id')=='__media_uploads':
                FileStorage(Path(config.MEDIA_ROOT)/'panoramas'/'incoming').delete_file(source['key'])
            elif not source:self.storage.delete_file(res["filename"])
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def update_pano(self, pano_id):
        return jsonify({"status": "error", "message": "Update not implemented"}), 501

    def _insert_pano_db(self, filename, path, lat, lon, alt, direction, timestamp, metadata=None, tags=""):
        metadata=metadata or {}
        query = 'INSERT INTO public.photos_4326 (geom, path, filename, directory, altitude, direction, rotation, longitude, latitude, "timestamp", "order") VALUES (ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326), %s, %s, %s, %s, %s, 0, %s, %s, %s, 0)'
        values = (float(lon), float(lat), float(alt or 0), path, filename, 'panoramas', float(alt or 0), float(direction or 0), str(lon), str(lat), timestamp or datetime.now())
        with self.db.cursor(write=True) as cursor:
            cursor.execute(query + ' RETURNING id', values)
            identifier=cursor.fetchone()['id']
            cursor.execute('UPDATE public.photos_4326 SET media_type=%s,width=%s,height=%s,tags=%s WHERE id=%s',
                (metadata.get('media_type'),metadata.get('width'),metadata.get('height'),tags,identifier))
            cursor.execute("INSERT INTO system_events(service,message) VALUES ('upload',%s)",(f'Файл №{identifier} сохранён без обработки.',))
            return identifier

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
