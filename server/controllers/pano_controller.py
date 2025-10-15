# ./backend/controllers/pano_controller.py

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import io
import piexif
from PIL import Image
from datetime import datetime
from managers.pano_manager import PanoManager
from database import Database
import config
from storage import LocalStorage
from models.pano import Pano

pano_blueprint = Blueprint("pano", __name__)

class PanoController:
    def __init__(self):
        self.db = Database()
        self.pano_manager = PanoManager(self.db)
        self.storage = LocalStorage(config.PANO_FOLDER)

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
        Возвращает краткий список панорам (id, latitude, longitude).
        """
        try:
            rows = self.pano_manager.get_pano_list()
            panoramas = []
            for row in rows:
                panoramas.append({
                    "id": row["id"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"]
                })
            return jsonify(panoramas)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_pano_info(self, pano_id):
        """
        Возвращает информацию о конкретной панораме (без поля 'url', если оно есть).
        """
        try:
            row = self.pano_manager.get_pano_by_id(pano_id)
            if row:
                row_dict = dict(row)
                row_dict.pop("url", None)
                return jsonify(row_dict)
            else:
                return jsonify({"error": "Panorama not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def download_pano_file(self, pano_id):
        """
        Отдаёт файл панорамы (JPG), если он существует в локальном хранилище.
        """
        try:
            row = self.pano_manager.get_pano_by_id(pano_id)
            if not row:
                return jsonify({"error": "Panorama not found"}), 404

            filename = row["filename"]
            file_type = row["file_type"] if row["file_type"] else "application/octet-stream"
            return self.storage.send_local_file(filename, mimetype=file_type)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def upload_pano_files(self):
        """
        Загрузка панорамных фото (JPEG).
        """
        if request.method == "OPTIONS":
            return "", 200

        uploaded_files = request.files.getlist("files")
        tags = request.form.get("tags", "")
        user_id = request.form.get("user_id", 1)

        successful_uploads = []
        failed_uploads = []
        skipped_files = []

        for file in uploaded_files:
            original_filename = file.filename
            try:
                file_content = file.read()
                file_stream = io.BytesIO(file_content)
                file_stream.seek(0)

                with Image.open(file_stream) as img:
                    # Проверка EXIF
                    if "exif" not in img.info:
                        raise ValueError("Файл без EXIF данных")

                    exif_dict = piexif.load(img.info["exif"])

                    # Извлекаем GPS
                    latitude, longitude, altitude = self._get_gps_coordinates(exif_dict)
                    if latitude is None or longitude is None:
                        raise ValueError("Файл без GPS координат")

                    file_size = len(file_content)
                    file_type = file.mimetype or "image/jpeg"
                    width, height = img.width, img.height
                    first_photo_date = self._extract_datetime_original(exif_dict)
                    new_filename = self._generate_filename(original_filename, first_photo_date)
                    model = self._get_model(exif_dict)
                    focal_length = self._get_focal_length(exif_dict)

                    # Сохраняем локально
                    file_save_stream = io.BytesIO(file_content)
                    self.storage.save_file(file_save_stream, new_filename)

                    # Запись в БД
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
                    self.pano_manager.create_pano(pano_obj)

                    successful_uploads.append(original_filename)
            except Exception as e:
                error_message = f"Ошибка при обработке файла {original_filename}: {str(e)}"
                print(error_message)
                failed_uploads.append(original_filename)
                skipped_files.append(error_message)

        return jsonify({
            "message": "Отчет о загрузке файлов",
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "skipped_files": skipped_files
        }), 200

    def update_pano(self, pano_id):
        """
        Обновляет некоторые поля панорамы (например, filename, latitude, longitude, tags).
        Ожидает JSON: {"filename": "...", "latitude":..., "longitude":..., "tags":"..."}
        """
        try:
            data = request.json
            existing = self.pano_manager.get_pano_by_id(pano_id)
            if not existing:
                return jsonify({"error": "Panorama not found"}), 404

            updated_fields = {}
            for field in ["filename", "latitude", "longitude", "tags"]:
                if field in data:
                    updated_fields[field] = data[field]

            self.pano_manager.update_pano(pano_id, updated_fields)
            return jsonify({"status": "success", "message": "Panorama updated"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def delete_pano(self, pano_id):
        """
        Удаляет панораму по её ID.
        """
        try:
            existing = self.pano_manager.get_pano_by_id(pano_id)
            if not existing:
                return jsonify({"error": "Panorama not found"}), 404

            self.pano_manager.delete_pano(pano_id)
            return jsonify({"status": "success", "message": "Panorama deleted"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ===== Вспомогательные методы =====

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
            altitude = alt[0] / alt[1] if isinstance(alt, tuple) else alt

        return (latitude, longitude, altitude)

    def _convert_to_degrees(self, value):
        """
        Преобразует GPS-координаты из формата EXIF в градусы (float).
        """
        d, m, s = value
        return d[0] / d[1] + (m[0] / m[1]) / 60 + (s[0] / s[1]) / 3600

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
        import os
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
            if isinstance(focal_length, tuple):
                return focal_length[0] / focal_length[1]
            return focal_length
        return None

PanoController.register_routes(pano_blueprint)