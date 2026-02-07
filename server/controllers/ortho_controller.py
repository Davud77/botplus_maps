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
        
        # Локальное хранилище (используется для временных файлов GDAL и хранения тайлов)
        self.storage = LocalStorage(config.ORTHO_FOLDER)
        
        # MinIO хранилище (для постоянного хранения оригиналов ортофотопланов)
        self.minio = MinioStorage()
        
        # При инициализации проверяем и создаем бакет 'orthophotos', если нужно
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
        
        # 2. Загрузка (Upload)
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

        # 7. Тайлы (XYZ)
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
                # Безопасный парсинг границ
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
    # 2. Загрузка GeoTIFF (Основная логика)
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
            try:
                logs.append(f"Обработка файла: {original_filename}")
                base_name, ext = os.path.splitext(original_filename)

                # 1. Временное сохранение на диск (GDAL требует путь к файлу)
                input_path = os.path.join(config.ORTHO_FOLDER, original_filename)
                file.save(input_path)
                logs.append(f"Временный файл сохранен: {input_path}")

                # 2. Проверка проекции и конвертация (Warp) в EPSG:3857
                current_crs = self._get_crs_from_gdalinfo(input_path)
                final_tiff_filename = f"{base_name}_3857.tif"
                final_tiff_path = os.path.join(config.ORTHO_FOLDER, final_tiff_filename)

                if current_crs != "EPSG:3857":
                    logs.append(f"Проекция {current_crs}. Выполняем Warp в EPSG:3857...")
                    try:
                        self._warp_to_mercator(input_path, final_tiff_path)
                    except subprocess.CalledProcessError as e:
                        raise Exception("Ошибка gdalwarp. Возможно, файл не имеет геопривязки.")
                    
                    # Удаляем исходный файл, он больше не нужен
                    if os.path.exists(input_path):
                        os.remove(input_path)
                else:
                    os.rename(input_path, final_tiff_path)
                    logs.append("Проекция корректна.")

                # 3. Генерация превью (PNG)
                preview_filename = f"{base_name}_3857_preview.png"
                preview_path = os.path.join(config.ORTHO_FOLDER, preview_filename)
                self._create_preview(final_tiff_path, preview_path)
                logs.append("Превью создано.")

                # 4. Получение границ изображения (Bounds)
                bounds = self._get_bounds_from_gdalinfo(final_tiff_path)

                # 5. Сохранение в БД
                # ВАЖНО: передаем url=None, так как модель теперь это поддерживает
                ortho_obj = Ortho(
                    filename=final_tiff_filename, 
                    bounds=json.dumps(bounds),
                    url=None 
                )
                ortho_id = self.ortho_manager.insert_ortho(ortho_obj)
                logs.append(f"Запись добавлена в БД. ID={ortho_id}")

                # 6. Генерация тайлов (XYZ)
                # Тайлы генерируются локально в папку tiles/ID
                tiles_folder = os.path.join(config.TILES_FOLDER, str(ortho_id))
                os.makedirs(tiles_folder, exist_ok=True)
                logs.append("Генерация тайлов...")
                self._generate_tiles(final_tiff_path, tiles_folder, logs)

                # 7. Загрузка оригиналов в MinIO
                if self.minio.client:
                    logs.append("Загрузка в MinIO (бакет 'orthophotos')...")
                    
                    # Загрузка основного TIFF
                    with open(final_tiff_path, 'rb') as f:
                        self.minio.save_file(f, final_tiff_filename, content_type="image/tiff")
                    
                    # Загрузка превью PNG
                    with open(preview_path, 'rb') as f:
                        self.minio.save_file(f, preview_filename, content_type="image/png")
                    
                    logs.append("Файлы успешно загружены в облако.")

                    # 8. Очистка локальных оригиналов
                    # Тайлы оставляем, оригиналы удаляем, чтобы не забивать диск
                    if os.path.exists(final_tiff_path): os.remove(final_tiff_path)
                    if os.path.exists(preview_path): os.remove(preview_path)
                    logs.append("Локальные временные файлы удалены.")
                else:
                    logs.append("ПРЕДУПРЕЖДЕНИЕ: MinIO недоступен. Файлы остались на диске.")

                successful_uploads.append(original_filename)

            except Exception as err:
                error_msg = f"Ошибка обработки {original_filename}: {err}"
                print(error_msg)
                traceback.print_exc()
                logs.append(error_msg)
                failed_uploads.append(original_filename)

        # Восстанавливаем имя бакета
        self.minio.bucket_name = original_bucket_name

        return jsonify({
            "message": "Процесс завершен",
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

            # Пытаемся отдать из MinIO (бакет orthophotos)
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
            
            # Fallback: пробуем отдать локально (если вдруг файл остался)
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
    # 6. Удалить (БД + MinIO + Тайлы)
    # =========================================================================
    def delete_ortho(self, ortho_id):
        try:
            existing = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not existing:
                return jsonify({"error": "Not found"}), 404

            # 1. Удаляем локальные тайлы
            tiles_path = os.path.join(config.TILES_FOLDER, str(ortho_id))
            if os.path.exists(tiles_path):
                import shutil
                shutil.rmtree(tiles_path)

            # 2. Удаляем файлы из MinIO
            if self.minio.client:
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = "orthophotos"
                
                # Удаляем сам файл
                self.minio.delete_file(existing.filename)
                # Удаляем превью (предполагаем имя)
                preview_name = existing.filename.replace(".tif", "_preview.png")
                self.minio.delete_file(preview_name)
                
                self.minio.bucket_name = orig_bucket

            # 3. Удаляем запись из БД
            self.ortho_manager.delete_ortho(ortho_id)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 7. Получить тайл (Локально)
    # =========================================================================
    def get_ortho_tile(self, ortho_id, z, x, y):
        try:
            tile_path = os.path.join(config.TILES_FOLDER, str(ortho_id), str(z), str(x), f"{y}.png")
            if os.path.exists(tile_path):
                return self.storage.send_local_file(tile_path, mimetype="image/png")
            return self._tile_png_rgba_transparent()
        except Exception:
            return self._tile_png_rgba_transparent()


    # =========================================================================
    # Вспомогательные функции GDAL
    # =========================================================================
    def _warp_to_mercator(self, input_path, output_path):
        cmd = [
            "gdalwarp",
            "-t_srs", "EPSG:3857",
            "-r", "bilinear",
            "-co", "COMPRESS=DEFLATE",
            "-overwrite",
            input_path,
            output_path
        ]
        subprocess.check_call(cmd)

    def _create_preview(self, input_path, output_path):
        cmd = [
            "gdal_translate",
            "-of", "PNG",
            "-outsize", "2048", "0",
            input_path,
            output_path
        ]
        subprocess.check_call(cmd)

    def _generate_tiles(self, tiff_path, dest_folder, logs):
        import multiprocessing
        nproc = multiprocessing.cpu_count()
        cmd = [
            sys.executable,
            "-m", "osgeo_utils.gdal2tiles",
            "--profile=mercator",
            "--xyz",
            "--processes", str(nproc),
            "-z", "0-20",
            tiff_path,
            dest_folder
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"gdal2tiles error: {err}")
        logs.append("Тайлы успешно сгенерированы.")

    def _get_crs_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(["gdalinfo", "-json", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = process.communicate()
        try:
            data = json.loads(out)
            if "coordinateSystem" in data and "wkt" in data["coordinateSystem"]:
                return "EPSG:3857" if "3857" in data["coordinateSystem"]["wkt"] else "UNKNOWN"
            if "coordinateSystem" in data and "data" in data["coordinateSystem"]:
                 if data["coordinateSystem"]["data"].get("code") == 3857: return "EPSG:3857"
        except: pass
        return "UNKNOWN"

    def _get_bounds_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(["gdalinfo", "-json", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = process.communicate()
        try:
            data = json.loads(out)
            coords = data.get("cornerCoordinates", {})
            
            # Безопасное извлечение координат
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