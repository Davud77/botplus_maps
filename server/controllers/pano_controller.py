# ./backend/controllers/pano_controller.py

from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import io
import os
import piexif
from PIL import Image
from datetime import datetime
import psycopg2
import traceback

# Импорты ваших модулей
from managers.pano_manager import PanoManager
from storage import MinioStorage
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
        Использует DATABASE_URL из docker-compose (через PgBouncer).
        """
        dsn = os.environ.get("DATABASE_URL", "postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db")
        return psycopg2.connect(dsn)

    @staticmethod
    def register_routes(blueprint):
        controller = PanoController()
        # Список панорам (краткая инфа)
        blueprint.add_url_rule("/panoramas", view_func=controller.get_panoramas, methods=["GET"])
        # Информация о конкретной панораме
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.get_pano_info, methods=["GET"])
        # Скачать файл панорамы
        blueprint.add_url_rule("/pano_info/<int:pano_id>/download", view_func=controller.download_pano_file, methods=["GET"])
        # Загрузка новых панорам
        blueprint.add_url_rule("/upload", view_func=controller.upload_pano_files, methods=["POST", "OPTIONS"])
        # Обновить панораму
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.update_pano, methods=["PUT"])
        # Удалить панораму
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.delete_pano, methods=["DELETE"])

    def get_panoramas(self):
        """
        Возвращает краткий список панорам из PostGIS.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            manager = PanoManager(conn)
            rows = manager.get_pano_list()
            return jsonify(rows)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    def get_pano_info(self, pano_id):
        """
        Возвращает информацию о конкретной панораме.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            manager = PanoManager(conn)
            row = manager.get_pano_by_id(pano_id)
            
            if row:
                return jsonify(row)
            else:
                return jsonify({"error": "Panorama not found"}), 404
        except Exception as e:
            print(f"Error getting pano info: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    def download_pano_file(self, pano_id):
        """
        Скачивает файл из MinIO и отдает клиенту.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            manager = PanoManager(conn)
            row = manager.get_pano_by_id(pano_id)
            
            if not row:
                return jsonify({"error": "Panorama not found"}), 404

            filename = row["filename"]
            file_type = "image/jpeg"
            
            return self.storage.send_local_file(filename, mimetype=file_type)
        except Exception as e:
            print(f"Error downloading file: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    @cross_origin()
    def upload_pano_files(self):
        """
        Загрузка панорамных фото (JPEG) -> MinIO + PostGIS.
        """
        if request.method == "OPTIONS":
            return "", 200

        uploaded_files = request.files.getlist("files")
        tags = request.form.get("tags", "")
        
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
            manager = PanoManager(conn)

            for file in uploaded_files:
                original_filename = file.filename
                try:
                    file_content = file.read()
                    file_stream = io.BytesIO(file_content)
                    file_stream.seek(0)

                    with Image.open(file_stream) as img:
                        # 1. Проверка EXIF
                        if "exif" not in img.info:
                            raise ValueError("Файл без EXIF данных")

                        try:
                            exif_dict = piexif.load(img.info["exif"])
                        except Exception:
                            raise ValueError("Не удалось прочитать структуру EXIF")

                        # 2. Извлекаем GPS (Безопасно!)
                        latitude, longitude, altitude = self._get_gps_coordinates(exif_dict)
                        if latitude is None or longitude is None:
                            raise ValueError("Файл без валидных GPS координат")

                        file_size = len(file_content)
                        file_type = file.mimetype or "image/jpeg"
                        width, height = img.width, img.height
                        
                        first_photo_date = self._extract_datetime_original(exif_dict)
                        if not first_photo_date:
                            first_photo_date = datetime.now()

                        new_filename = self._generate_filename(original_filename, first_photo_date)
                        model = self._get_model(exif_dict)
                        focal_length = self._get_focal_length(exif_dict)

                        # 3. Сохраняем в MinIO
                        file_save_stream = io.BytesIO(file_content)
                        self.storage.save_file(file_save_stream, new_filename)

                        # 4. Запись в БД (PostGIS)
                        pano_obj = Pano(
                            filename=new_filename,
                            latitude=latitude,
                            longitude=longitude,
                            user_id=user_id,
                            file_type=file_type,
                            file_size=file_size,
                            width=width,
                            height=height,
                            first_photo_date=first_photo_date,
                            model=model,
                            altitude=altitude,
                            focal_length=focal_length,
                            tags=tags
                        )
                        manager.create_pano(pano_obj)

                        successful_uploads.append(original_filename)
                except Exception as e:
                    # Логируем стек ошибки для отладки
                    traceback.print_exc()
                    error_message = f"Ошибка ({original_filename}): {str(e)}"
                    print(error_message)
                    failed_uploads.append(original_filename)
                    skipped_files.append(error_message)

            return jsonify({
                "message": "Отчет о загрузке файлов",
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "skipped_files": skipped_files
            }), 200
            
        except Exception as e:
            return jsonify({"error": f"System error: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

    def update_pano(self, pano_id):
        """
        Обновляет некоторые поля панорамы.
        """
        conn = None
        try:
            data = request.json
            conn = self._get_db_connection()
            manager = PanoManager(conn)
            
            existing = manager.get_pano_by_id(pano_id)
            if not existing:
                return jsonify({"error": "Panorama not found"}), 404

            updated_fields = {}
            for field in ["filename", "latitude", "longitude", "tags"]:
                if field in data:
                    updated_fields[field] = data[field]

            manager.update_pano(pano_id, updated_fields)
            return jsonify({"status": "success", "message": "Panorama updated"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    def delete_pano(self, pano_id):
        """
        Удаляет панораму.
        """
        conn = None
        try:
            conn = self._get_db_connection()
            manager = PanoManager(conn)
            
            existing = manager.get_pano_by_id(pano_id)
            if not existing:
                return jsonify({"error": "Panorama not found"}), 404

            manager.delete_pano(pano_id)
            return jsonify({"status": "success", "message": "Panorama deleted"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if conn:
                conn.close()

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (С ЗАЩИТОЙ) =====

    def _safe_rational(self, value):
        """
        Безопасное чтение рациональных чисел из EXIF.
        Защищает от ошибки 'tuple index out of range', если формат (num,).
        """
        if isinstance(value, tuple):
            if len(value) >= 2:
                # Стандартный случай (числитель, знаменатель)
                if value[1] == 0: return 0.0
                return float(value[0]) / float(value[1])
            elif len(value) == 1:
                # Нестандартный случай (GoPro/Insta360): (число,)
                return float(value[0])
            else:
                return 0.0
        # Если пришло просто число
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_gps_coordinates(self, exif_dict):
        gps_ifd = exif_dict.get("GPS", {})
        latitude = longitude = altitude = None

        if piexif.GPSIFD.GPSLatitude in gps_ifd and piexif.GPSIFD.GPSLatitudeRef in gps_ifd:
            lat = gps_ifd[piexif.GPSIFD.GPSLatitude]
            lat_ref = gps_ifd[piexif.GPSIFD.GPSLatitudeRef].decode()
            latitude = self._convert_to_degrees(lat)
            if lat_ref != "N":
                latitude = -latitude

        if piexif.GPSIFD.GPSLongitude in gps_ifd and piexif.GPSIFD.GPSLongitudeRef in gps_ifd:
            lon = gps_ifd[piexif.GPSIFD.GPSLongitude]
            lon_ref = gps_ifd[piexif.GPSIFD.GPSLongitudeRef].decode()
            longitude = self._convert_to_degrees(lon)
            if lon_ref != "E":
                longitude = -longitude

        if piexif.GPSIFD.GPSAltitude in gps_ifd:
            alt = gps_ifd[piexif.GPSIFD.GPSAltitude]
            # [FIX] Используем безопасный метод
            altitude = self._safe_rational(alt)

        return (latitude, longitude, altitude)

    def _convert_to_degrees(self, value):
        """
        Преобразует GPS-координаты из формата EXIF (D, M, S) в градусы.
        """
        try:
            # value ожидается кортежем из 3 элементов
            if not isinstance(value, tuple) or len(value) < 3:
                return 0.0
            
            d, m, s = value
            # [FIX] Используем _safe_rational для каждого компонента
            d_val = self._safe_rational(d)
            m_val = self._safe_rational(m)
            s_val = self._safe_rational(s)
            
            return d_val + (m_val / 60.0) + (s_val / 3600.0)
        except Exception as e:
            print(f"Error converting GPS: {e}")
            return 0.0

    def _extract_datetime_original(self, exif_dict):
        exif_data = exif_dict.get("Exif", {})
        date_str = exif_data.get(piexif.ExifIFD.DateTimeOriginal, None)
        if date_str:
            date_str = self._sanitize_string(date_str.decode("utf-8", "ignore"))
            try:
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                return None
        return None

    def _generate_filename(self, original_filename, dt=None):
        name, ext = os.path.splitext(original_filename)
        if dt:
            date_str = dt.strftime("%Y%m%d")
            return f"{name}_{date_str}{ext}"
        else:
            return original_filename

    def _sanitize_string(self, val):
        return val.replace("\x00", "")

    def _get_model(self, exif_dict):
        zero_ifd = exif_dict.get("0th", {})
        model = zero_ifd.get(piexif.ImageIFD.Model, None)
        if model:
            model = model.decode("utf-8", "ignore")
            model = self._sanitize_string(model)
        return model

    def _get_focal_length(self, exif_dict):
        exif_data = exif_dict.get("Exif", {})
        focal_length = exif_data.get(piexif.ExifIFD.FocalLength, None)
        if focal_length:
            return self._safe_rational(focal_length)
        return None

PanoController.register_routes(pano_blueprint)