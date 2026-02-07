# ./backend/controllers/ortho_controller.py

from flask import Blueprint, jsonify, request, make_response
from managers.ortho_manager import OrthoManager
from database import Database
from models.ortho import Ortho
# Импортируем оба класса хранилища
from storage import LocalStorage, MinioStorage
import config
import json
import subprocess
import os
import re
import sys
import traceback
from io import BytesIO
from PIL import Image

ortho_blueprint = Blueprint("ortho", __name__)

class OrthoController:
    def __init__(self):
        self.db = Database()
        self.ortho_manager = OrthoManager(self.db)
        
        # Локальное хранилище (используется только для временного анализа GDAL)
        self.storage = LocalStorage(config.ORTHO_FOLDER)
        
        # MinIO хранилище (для постоянного хранения файлов)
        self.minio = MinioStorage()
        
        # При инициализации проверяем и создаем бакет 'orthophotos'
        if self.minio.client:
            try:
                if not self.minio.client.bucket_exists("orthophotos"):
                    self.minio.client.make_bucket("orthophotos")
                    print("Bucket 'orthophotos' created successfully.")
            except Exception as e:
                print(f"MinIO init warning: {e}")

    @staticmethod
    def register_routes(blueprint):
        controller = OrthoController()

        # 1. Список
        blueprint.add_url_rule("/orthophotos", 
                               view_func=controller.get_orthophotos, 
                               methods=["GET"])
        
        # 2. Загрузка (Upload -> COG Convert -> Bounds -> DB -> MinIO)
        blueprint.add_url_rule("/upload_ortho", 
                               view_func=controller.upload_ortho, 
                               methods=["POST"])
        
        # 3. Инфо
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.get_ortho, 
                               methods=["GET"])
        
        # 4. Скачать файл
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/download", 
                               view_func=controller.download_ortho_file, 
                               methods=["GET"])
        
        # 5. Обновить
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.update_ortho, 
                               methods=["PUT"])
        
        # 6. Удалить
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.delete_ortho, 
                               methods=["DELETE"])

        # 7. Тайлы (Заглушка, теперь тайлы отдает TiTiler, но роут оставим для совместимости)
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>.png",
                               view_func=controller.get_ortho_tile,
                               methods=["GET"])


    # =========================================================================
    # 1. Список ортофотопланов
    # =========================================================================
    def get_orthophotos(self):
        try:
            orthos = self.ortho_manager.get_all_orthos()
            results = []
            for o in orthos:
                b = None
                if o.bounds:
                    try:
                        b = json.loads(o.bounds)
                    except Exception:
                        pass 
                
                item = {
                    "id": o.id,
                    "filename": o.filename,
                    "url": f"/api/orthophotos/{o.id}/download",
                    "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                    "upload_date": str(o.upload_date) if hasattr(o, 'upload_date') else None
                }
                results.append(item)
            return jsonify(results), 200
        except Exception as e:
            print("ERROR in get_orthophotos:")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 2. Загрузка GeoTIFF с конвертацией в COG (Cloud Optimized GeoTIFF)
    # =========================================================================
    def upload_ortho(self):
        uploaded_files = request.files.getlist("files")
        successful_uploads = []
        failed_uploads = []
        logs = []

        if not uploaded_files:
            return jsonify({"message": "Нет файлов для загрузки"}), 400

        # Сохраняем текущее имя бакета и переключаемся на 'orthophotos'
        original_bucket_name = self.minio.bucket_name
        self.minio.bucket_name = "orthophotos"

        for file in uploaded_files:
            original_filename = file.filename
            
            # Генерируем имя для COG версии (например, map.tif -> map_cog.tif)
            name_part, ext_part = os.path.splitext(original_filename)
            cog_filename = f"{name_part}_cog.tif"

            try:
                logs.append(f"Обработка файла: {original_filename}")
                
                # 1. Временное сохранение исходника на диск (для GDAL)
                input_path = os.path.join(config.ORTHO_FOLDER, original_filename)
                cog_path = os.path.join(config.ORTHO_FOLDER, cog_filename)
                
                file.save(input_path)
                logs.append(f"Временный файл сохранен: {input_path}")

                # 2. КОНВЕРТАЦИЯ В COG
                # TiTiler требует COG для быстрой работы с MinIO без скачивания всего файла
                logs.append("Начинаю конвертацию в COG (Cloud Optimized GeoTIFF)...")
                
                # gdal_translate -of COG -co COMPRESS=DEFLATE ...
                cmd = [
                    "gdal_translate", input_path, cog_path,
                    "-of", "COG",
                    "-co", "COMPRESS=DEFLATE",        # Сжатие
                    "-co", "PREDICTOR=2",             # Оптимизация для растров
                    "-co", "NUM_THREADS=ALL_CPUS",    # Использовать все ядра
                    "-co", "OVERVIEWS=IGNORE_EXISTING"
                ]
                
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                if process.returncode != 0:
                    raise Exception(f"GDAL Error: {process.stderr}")
                
                logs.append("Конвертация в COG успешно завершена.")

                # 3. Считываем границы (Bounds) уже с НОВОГО COG файла
                bounds = self._get_bounds_from_gdalinfo(cog_path)
                logs.append("Границы (bounds) считаны.")

                # 4. Сохранение в БД
                # Важно: сохраняем имя именно COG файла, так как TiTiler будет искать его
                ortho_obj = Ortho(
                    filename=cog_filename, 
                    bounds=json.dumps(bounds),
                    url=None 
                )
                ortho_id = self.ortho_manager.insert_ortho(ortho_obj)
                logs.append(f"Запись добавлена в БД. ID={ortho_id}")

                # 5. Загрузка COG в MinIO
                if self.minio.client:
                    logs.append("Загрузка COG в MinIO (бакет 'orthophotos')...")
                    
                    with open(cog_path, 'rb') as f:
                        self.minio.save_file(f, cog_filename, content_type="image/tiff")
                    
                    logs.append("Файл успешно загружен в облако.")

                    # 6. Очистка: удаляем оба временных файла
                    if os.path.exists(input_path): os.remove(input_path)
                    if os.path.exists(cog_path): os.remove(cog_path)
                    logs.append("Локальные временные файлы удалены.")
                else:
                    logs.append("ПРЕДУПРЕЖДЕНИЕ: MinIO недоступен. Файл остался на диске сервера.")

                successful_uploads.append(original_filename)

            except Exception as err:
                error_msg = f"Ошибка обработки {original_filename}: {err}"
                print(error_msg)
                traceback.print_exc()
                logs.append(error_msg)
                failed_uploads.append(original_filename)
                
                # Попытка удалить мусор при ошибке
                if 'input_path' in locals() and os.path.exists(input_path):
                    try: os.remove(input_path)
                    except: pass
                if 'cog_path' in locals() and os.path.exists(cog_path):
                    try: os.remove(cog_path)
                    except: pass

        # Восстанавливаем имя бакета
        self.minio.bucket_name = original_bucket_name

        return jsonify({
            "message": "Загрузка завершена",
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "logs": logs
        }), 200


    # =========================================================================
    # 3. Получить инфо
    # =========================================================================
    def get_ortho(self, ortho_id):
        try:
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Not found"}), 404

            b = json.loads(ortho.bounds) if ortho.bounds else None
            result = {
                "id": ortho.id,
                "filename": ortho.filename,
                "url": f"/api/orthophotos/{ortho.id}/download",
                "bounds": b
            }
            return jsonify(result), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 4. Скачать файл (из MinIO)
    # =========================================================================
    def download_ortho_file(self, ortho_id):
        try:
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Not found"}), 404

            # Пытаемся отдать из MinIO
            original_bucket = self.minio.bucket_name
            self.minio.bucket_name = "orthophotos"
            
            response = None
            if self.minio.client:
                try:
                    response = self.minio.send_local_file(ortho.filename, mimetype="image/tiff")
                except Exception as e:
                    print(f"MinIO download failed: {e}")
            
            self.minio.bucket_name = original_bucket
            
            if response:
                return response
            
            # Fallback: локально
            return self.storage.send_local_file(ortho.filename, mimetype="image/tiff")
            
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 5. Обновить данные
    # =========================================================================
    def update_ortho(self, ortho_id):
        try:
            data = request.json
            self.ortho_manager.update_ortho(ortho_id, data)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 6. Удалить (БД + MinIO)
    # =========================================================================
    def delete_ortho(self, ortho_id):
        try:
            existing = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not existing:
                return jsonify({"error": "Not found"}), 404

            # 1. Удаляем из MinIO
            if self.minio.client:
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = "orthophotos"
                
                self.minio.delete_file(existing.filename)
                
                self.minio.bucket_name = orig_bucket

            # 2. Удаляем запись из БД
            self.ortho_manager.delete_ortho(ortho_id)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 7. Получить тайл (Заглушка)
    # =========================================================================
    def get_ortho_tile(self, ortho_id, z, x, y):
        # Так как тайлы теперь отдает сервис TiTiler, этот метод
        # возвращает прозрачный пиксель (заглушка для совместимости)
        return self._tile_png_rgba_transparent()


    # =========================================================================
    # Вспомогательные функции GDAL (только чтение инфо)
    # =========================================================================
    def _get_crs_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(["gdalinfo", "-json", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = process.communicate()
        try:
            data = json.loads(out)
            if "coordinateSystem" in data and "wkt" in data["coordinateSystem"]:
                # Просто возвращаем WKT или код, если есть
                wkt = data["coordinateSystem"]["wkt"]
                if "EPSG" in wkt: return "EPSG Found"
                return "Unknown/Custom"
            if "coordinateSystem" in data and "data" in data["coordinateSystem"]:
                 code = data["coordinateSystem"]["data"].get("code")
                 if code: return f"EPSG:{code}"
        except: pass
        return "UNKNOWN"

    def _get_bounds_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(["gdalinfo", "-json", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = process.communicate()
        try:
            data = json.loads(out)
            coords = data.get("cornerCoordinates", {})
            
            def get_coord(key, idx):
                val = coords.get(key)
                if val and len(val) > idx: return val[idx]
                return 0.0

            all_x = [get_coord("upperLeft", 0), get_coord("lowerRight", 0), get_coord("upperRight", 0), get_coord("lowerLeft", 0)]
            all_y = [get_coord("upperLeft", 1), get_coord("lowerRight", 1), get_coord("upperRight", 1), get_coord("lowerLeft", 1)]
            
            return {
                "north": max(all_y), 
                "south": min(all_y), 
                "east": max(all_x), 
                "west": min(all_x)
            }
        except:
            return {"north": 0, "south": 0, "east": 0, "west": 0}

    def _tile_png_rgba_transparent(self):
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        response = make_response(buf.read())
        response.headers.set("Content-Type", "image/png")
        return response

# Регистрация роутов
OrthoController.register_routes(ortho_blueprint)