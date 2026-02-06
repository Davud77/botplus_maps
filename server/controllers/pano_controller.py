from flask import Blueprint, request, jsonify, send_file
# ВАЖНО: Убедитесь, что установлен пакет flask-cors (pip install flask-cors)
from flask_cors import cross_origin
import io
import os
import piexif
from PIL import Image
from datetime import datetime
import psycopg2
import traceback
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорты ваших модулей
from storage import MinioStorage
# PanoManager больше не используется для чтения списка, так как мы пишем прямой SQL для фильтрации
from managers.pano_manager import PanoManager 
from models.pano import Pano
import config

pano_blueprint = Blueprint("pano", __name__)

class PanoController:
    def __init__(self):
        # Инициализация хранилища S3 (MinIO)
        self.storage = MinioStorage()

    def _get_db_connection(self):
        """
        Создает соединение с PostgreSQL.
        """
        dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/qgisdb")
        return psycopg2.connect(dsn)

    @staticmethod
    def register_routes(blueprint):
        controller = PanoController()
        blueprint.add_url_rule("/panoramas", view_func=controller.get_panoramas, methods=["GET"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.get_pano_info, methods=["GET"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>/download", view_func=controller.download_pano_file, methods=["GET"])
        blueprint.add_url_rule("/upload", view_func=controller.upload_pano_files, methods=["POST", "OPTIONS"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.update_pano, methods=["PUT"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.delete_pano, methods=["DELETE"])

    @cross_origin()
    def get_panoramas(self):
        """
        Возвращает список панорам. 
        Поддерживает фильтрацию по Bounding Box (north, south, east, west) для карты.
        """
        conn = None
        try:
            # 1. Считываем параметры фильтрации из URL
            north = request.args.get('north', type=float)
            south = request.args.get('south', type=float)
            east = request.args.get('east', type=float)
            west = request.args.get('west', type=float)
            limit = request.args.get('limit', type=int, default=1000)

            conn = self._get_db_connection()
            cur = conn.cursor()

            # 2. Строим запрос
            if north is not None and south is not None:
                # Поиск внутри прямоугольника (ST_MakeEnvelope: xmin, ymin, xmax, ymax, srid)
                query = """
                    SELECT 
                        id, 
                        latitude::float, 
                        longitude::float, 
                        filename, 
                        directory,
                        "timestamp"
                    FROM public.photos_4326
                    WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                    LIMIT %s
                """
                # Порядок: West(Lon), South(Lat), East(Lon), North(Lat)
                params = (west, south, east, north, limit)
            else:
                # Если границы не заданы, возвращаем последние N записей
                query = """
                    SELECT 
                        id, 
                        latitude::float, 
                        longitude::float, 
                        filename, 
                        directory,
                        "timestamp"
                    FROM public.photos_4326
                    ORDER BY id DESC
                    LIMIT %s
                """
                params = (limit,)

            cur.execute(query, params)
            rows = cur.fetchall()

            # 3. Формируем ответ JSON
            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "latitude": row[1],
                    "longitude": row[2],
                    "filename": row[3],
                    "directory": row[4],
                    "timestamp": row[5].isoformat() if row[5] else None
                })

            return jsonify(results)

        except Exception as e:
            logger.error(f"Error getting panoramas: {e}")
            logger.debug(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    @cross_origin()
    def get_pano_info(self, pano_id):
        """
        Возвращает полную информацию о конкретной панораме.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            query = """
                SELECT id, latitude, longitude, altitude, direction, filename, directory, "timestamp"
                FROM public.photos_4326 
                WHERE id = %s
            """
            cur.execute(query, (pano_id,))
            row = cur.fetchone()
            
            if row:
                data = {
                    "id": row[0],
                    "latitude": float(row[1]) if row[1] else 0,
                    "longitude": float(row[2]) if row[2] else 0,
                    "altitude": float(row[3]) if row[3] else 0,
                    "direction": float(row[4]) if row[4] else 0,
                    "filename": row[5],
                    "directory": row[6],
                    "timestamp": row[7].isoformat() if row[7] else None
                }
                return jsonify(data)
            else:
                return jsonify({"error": "Panorama not found"}), 404
        except Exception as e:
            logger.error(f"Error getting pano info: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    @cross_origin()
    def download_pano_file(self, pano_id):
        """
        Скачивает файл из MinIO.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Ищем имя файла по ID
            cur.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cur.fetchone()
            
            if not res:
                return jsonify({"error": "Panorama file record not found"}), 404

            filename = res[0]
            file_type = "image/jpeg"
            
            return self.storage.send_local_file(filename, mimetype=file_type)
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    @cross_origin()
    def upload_pano_files(self):
        """
        Загрузка: EXIF -> MinIO -> PostGIS.
        """
        if request.method == "OPTIONS":
            return "", 200

        uploaded_files = request.files.getlist("files")
        
        # Данные формы (теги, user_id)
        # tags = request.form.get("tags", "") 
        try:
            user_id = int(request.form.get("user_id", 1))
        except ValueError:
            user_id = 1

        successful_uploads = []
        failed_uploads = []
        skipped_files = []

        conn = None
        try:
            conn = self._get_db_connection()
            conn.autocommit = False # Транзакция

            for file in uploaded_files:
                original_filename = file.filename
                new_filename = None
                
                try:
                    file_content = file.read()
                    file_stream = io.BytesIO(file_content)
                    file_stream.seek(0)

                    with Image.open(file_stream) as img:
                        # 1. EXIF
                        if "exif" not in img.info:
                            raise ValueError("Файл без EXIF данных")
                        try:
                            exif_dict = piexif.load(img.info["exif"])
                        except Exception:
                            raise ValueError("Не удалось прочитать структуру EXIF")

                        # 2. GPS
                        latitude, longitude, altitude = self._get_gps_coordinates(exif_dict)
                        direction = self._get_direction(exif_dict)

                        if latitude is None or longitude is None:
                            raise ValueError("Файл без валидных GPS координат")

                        first_photo_date = self._extract_datetime_original(exif_dict)
                        if not first_photo_date:
                            first_photo_date = datetime.now()

                        new_filename = self._generate_filename(original_filename, first_photo_date)
                        
                        # 3. MinIO
                        file_save_stream = io.BytesIO(file_content)
                        self.storage.save_file(file_save_stream, new_filename)
                        
                        file_path = f"panoramas/{new_filename}"

                        # 4. PostGIS
                        self._insert_into_photos_4326(
                            conn,
                            filename=new_filename,
                            path=file_path,
                            directory="panoramas",
                            lat=latitude,
                            lon=longitude,
                            alt=altitude,
                            direction=direction,
                            timestamp=first_photo_date
                        )

                        conn.commit()
                        successful_uploads.append(original_filename)
                        logger.info(f"Uploaded: {original_filename} as {new_filename}")

                except Exception as e:
                    conn.rollback()
                    # Откат MinIO
                    if new_filename:
                        try:
                            if hasattr(self.storage, 'delete_file'):
                                self.storage.delete_file(new_filename)
                            elif hasattr(self.storage, 'remove_file'):
                                self.storage.remove_file(new_filename)
                        except Exception as minio_e:
                            logger.error(f"Rollback failed for {new_filename}: {minio_e}")

                    error_msg = f"Ошибка ({original_filename}): {str(e)}"
                    print(error_msg)
                    logger.error(error_msg)
                    logger.debug(traceback.format_exc())
                    
                    failed_uploads.append(original_filename)
                    skipped_files.append(error_msg)

            return jsonify({
                "message": "Отчет о загрузке файлов",
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "skipped_files": skipped_files
            }), 200
            
        except Exception as e:
            if conn: conn.rollback()
            logger.critical(f"System error upload: {e}")
            return jsonify({"error": f"System error: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

    @cross_origin()
    def update_pano(self, pano_id):
        # Заглушка
        return jsonify({"status": "error", "message": "Not implemented"}), 501

    @cross_origin()
    def delete_pano(self, pano_id):
        """
        Удаляет панораму (БД + MinIO).
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cur.fetchone()
            if not res:
                return jsonify({"error": "Panorama not found"}), 404

            filename = res[0]

            cur.execute("DELETE FROM public.photos_4326 WHERE id = %s", (pano_id,))
            conn.commit()

            try:
                if hasattr(self.storage, 'delete_file'):
                    self.storage.delete_file(filename)
                elif hasattr(self.storage, 'remove_file'):
                    self.storage.remove_file(filename)
            except Exception as e:
                logger.warning(f"DB record deleted, but MinIO file delete failed: {e}")

            return jsonify({"status": "success", "message": "Panorama deleted"}), 200
        except Exception as e:
            if conn: conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====

    def _insert_into_photos_4326(self, conn, filename, path, directory, lat, lon, alt, direction, timestamp):
        # Вставляем данные. ID генерируется автоматически (SERIAL).
        query = """
        INSERT INTO public.photos_4326 (
            geom, 
            path, 
            filename, 
            directory, 
            altitude, 
            direction, 
            rotation, 
            longitude, 
            latitude, 
            "timestamp"
        ) VALUES (
            ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326),
            %s, %s, %s, 
            %s, %s, %s, 
            %s, %s, %s
        )
        """
        
        alt_val = float(alt) if alt is not None else 0.0
        dir_val = float(direction) if direction is not None else 0.0
        rot_val = 0
        
        lon_str = str(lon)
        lat_str = str(lat)
        
        values = (
            float(lon), float(lat), alt_val,  # geom
            path,                             # path
            filename,                         # filename
            directory,                        # directory
            alt_val,                          # altitude
            dir_val,                          # direction
            rot_val,                          # rotation
            lon_str,                          # longitude
            lat_str,                          # latitude
            timestamp                         # timestamp
        )
        
        with conn.cursor() as cur:
            cur.execute(query, values)

    def _safe_rational(self, value):
        if value is None: return 0.0
        try:
            if isinstance(value, tuple):
                if len(value) >= 2:
                    den = float(value[1])
                    if den == 0: return 0.0
                    return float(value[0]) / den
                elif len(value) == 1:
                    return float(value[0])
            return float(value)
        except Exception:
            return 0.0

    def _get_direction(self, exif_dict):
        gps_ifd = exif_dict.get("GPS", {})
        val = gps_ifd.get(17) or gps_ifd.get("GPSImgDirection")
        return self._safe_rational(val)

    def _get_gps_coordinates(self, exif_dict):
        gps_ifd = exif_dict.get("GPS", {})
        latitude = longitude = altitude = None

        if piexif.GPSIFD.GPSLatitude in gps_ifd:
            lat = gps_ifd[piexif.GPSIFD.GPSLatitude]
            try:
                lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
                if isinstance(lat_ref, bytes): lat_ref = lat_ref.decode()
            except: lat_ref = "N"
            latitude = self._convert_to_degrees(lat)
            if lat_ref != "N": latitude = -latitude

        if piexif.GPSIFD.GPSLongitude in gps_ifd:
            lon = gps_ifd[piexif.GPSIFD.GPSLongitude]
            try:
                lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
                if isinstance(lon_ref, bytes): lon_ref = lon_ref.decode()
            except: lon_ref = "E"
            longitude = self._convert_to_degrees(lon)
            if lon_ref != "E": longitude = -longitude

        if piexif.GPSIFD.GPSAltitude in gps_ifd:
            alt = gps_ifd[piexif.GPSIFD.GPSAltitude]
            altitude = self._safe_rational(alt)
        else:
            altitude = 0.0

        return (latitude, longitude, altitude)

    def _convert_to_degrees(self, value):
        try:
            if not isinstance(value, tuple): return float(value)
            if len(value) < 3: return 0.0
            d = self._safe_rational(value[0])
            m = self._safe_rational(value[1])
            s = self._safe_rational(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        except Exception as e:
            logger.debug(f"GPS error: {e}")
            return 0.0

    def _extract_datetime_original(self, exif_dict):
        exif_data = exif_dict.get("Exif", {})
        date_str = exif_data.get(piexif.ExifIFD.DateTimeOriginal)
        if date_str:
            if isinstance(date_str, bytes):
                date_str = date_str.decode("utf-8", "ignore")
            date_str = self._sanitize_string(date_str)
            try:
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                return None
        return None

    def _generate_filename(self, original_filename, dt=None):
        name, ext = os.path.splitext(original_filename)
        name = "".join(c for c in name if c.isalnum() or c in ('-', '_'))
        if dt:
            date_str = dt.strftime("%Y%m%d_%H%M%S")
            return f"{name}_{date_str}{ext}"
        return f"{name}_{int(datetime.now().timestamp())}{ext}"

    def _sanitize_string(self, val):
        return val.replace("\x00", "").strip()

    def _get_model(self, exif_dict):
        zero_ifd = exif_dict.get("0th", {})
        model = zero_ifd.get(piexif.ImageIFD.Model, None)
        if model:
            if isinstance(model, bytes): model = model.decode("utf-8", "ignore")
            return self._sanitize_string(model)
        return "Unknown"

    def _get_focal_length(self, exif_dict):
        exif_data = exif_dict.get("Exif", {})
        focal = exif_data.get(piexif.ExifIFD.FocalLength)
        if focal: return self._safe_rational(focal)
        return None

PanoController.register_routes(pano_blueprint)