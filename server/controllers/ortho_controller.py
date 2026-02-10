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
# [FIX] Добавляем requests для проксирования
import requests

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

        # 7. Тайлы (ПРОКСИ на TiTiler)
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>.png",
                               view_func=controller.get_ortho_tile,
                               methods=["GET"])
                               
        # 8. Перепроецирование (Новый роут)
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/reproject", 
                               view_func=controller.reproject_ortho, 
                               methods=["POST"])


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
                
                # Пытаемся получить CRS из объекта или угадать по имени файла
                crs_val = getattr(o, 'crs', None)
                if not crs_val and o.filename and "_3857" in o.filename:
                    crs_val = "EPSG:3857"

                item = {
                    "id": o.id,
                    "filename": o.filename,
                    "url": f"/api/orthophotos/{o.id}/download",
                    "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                    "crs": crs_val,
                    "upload_date": str(o.upload_date) if hasattr(o, 'upload_date') else None
                }
                results.append(item)
            return jsonify(results), 200
        except Exception as e:
            print("ERROR in get_orthophotos:")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 2. Загрузка GeoTIFF с конвертацией в COG
    # =========================================================================
    def upload_ortho(self):
        uploaded_files = request.files.getlist("files")
        successful_uploads = []
        failed_uploads = []
        logs = []

        if not uploaded_files:
            return jsonify({"message": "Нет файлов для загрузки"}), 400

        original_bucket_name = self.minio.bucket_name
        self.minio.bucket_name = "orthophotos"
        
        # Используем папку data/temp/orthos
        temp_dir = "data/temp/orthos" 
        
        if not os.path.exists(temp_dir):
            try:
                os.makedirs(temp_dir, exist_ok=True)
                logs.append(f"Создана временная директория: {temp_dir}")
            except OSError as e:
                return jsonify({"error": f"Не удалось создать директорию {temp_dir}: {e}"}), 500

        for file in uploaded_files:
            original_filename = file.filename
            
            name_part, ext_part = os.path.splitext(original_filename)
            cog_filename = f"{name_part}_cog.tif"

            try:
                logs.append(f"Обработка файла: {original_filename}")
                
                input_path = os.path.join(temp_dir, original_filename)
                cog_path = os.path.join(temp_dir, cog_filename)
                
                # 1. Сохраняем локально
                file.save(input_path)
                logs.append(f"Временный файл сохранен: {input_path}")

                # 2. Определяем проекцию (включая проверку на МСК-05)
                initial_crs = self._get_crs_from_gdalinfo(input_path)
                logs.append(f"Обнаружена проекция: {initial_crs}")

                # 3. КОНВЕРТАЦИЯ В COG
                logs.append("Начинаю конвертацию в COG...")
                
                cmd = [
                    "gdal_translate", input_path, cog_path,
                    "-of", "COG",
                    "-co", "COMPRESS=DEFLATE",
                    "-co", "PREDICTOR=2",
                    "-co", "NUM_THREADS=ALL_CPUS",
                    "-co", "OVERVIEWS=IGNORE_EXISTING"
                ]
                
                process = subprocess.run(cmd, capture_output=True, text=True)
                if process.returncode != 0:
                    raise Exception(f"GDAL Error: {process.stderr}")
                
                logs.append("Конвертация в COG успешно завершена.")

                # 4. Считываем границы
                bounds = self._get_bounds_from_gdalinfo(cog_path)
                logs.append("Границы (bounds) считаны.")

                # 5. Сохранение в БД
                ortho_obj = Ortho(
                    filename=cog_filename, 
                    bounds=json.dumps(bounds),
                    url=None 
                )
                # Присваиваем CRS объекту (манагер сам разберется, сохранять или нет)
                ortho_obj.crs = initial_crs
                
                ortho_id = self.ortho_manager.insert_ortho(ortho_obj)
                
                # Если insert не поддерживает CRS сразу (старый код), обновляем через update
                try:
                    self.ortho_manager.update_ortho(ortho_id, {"crs": initial_crs})
                except:
                    pass

                logs.append(f"Запись добавлена в БД. ID={ortho_id}")

                # 6. Загрузка в MinIO
                if self.minio.client:
                    logs.append("Загрузка COG в MinIO...")
                    self.minio.client.fput_object(
                        "orthophotos", 
                        cog_filename, 
                        cog_path, 
                        content_type="image/tiff"
                    )
                    logs.append("Файл успешно загружен в облако.")

                    # Очистка
                    if os.path.exists(input_path): os.remove(input_path)
                    if os.path.exists(cog_path): os.remove(cog_path)
                    logs.append("Локальные временные файлы удалены.")
                else:
                    logs.append("ПРЕДУПРЕЖДЕНИЕ: MinIO недоступен.")

                successful_uploads.append(original_filename)

            except Exception as err:
                error_msg = f"Ошибка обработки {original_filename}: {err}"
                print(error_msg)
                traceback.print_exc()
                logs.append(error_msg)
                failed_uploads.append(original_filename)
                
                # Очистка при ошибке
                if 'input_path' in locals() and os.path.exists(input_path):
                    try: os.remove(input_path)
                    except: pass
                if 'cog_path' in locals() and os.path.exists(cog_path):
                    try: os.remove(cog_path)
                    except: pass

        self.minio.bucket_name = original_bucket_name

        return jsonify({
            "message": "Загрузка завершена",
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "logs": logs
        }), 200


    # =========================================================================
    # [НОВОЕ] Перепроецирование в EPSG:3857 (Google)
    # =========================================================================
    def reproject_ortho(self, ortho_id):
        temp_dir = "data/temp/orthos"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)

        try:
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Ortho not found"}), 404

            print(f"Starting reprojection for Ortho ID {ortho_id} ({ortho.filename})")

            # 1. Скачиваем файл из MinIO
            local_path = os.path.join(temp_dir, ortho.filename)
            self.minio.client.fget_object("orthophotos", ortho.filename, local_path)
            print(f"Downloaded to {local_path}")

            # 2. Формируем имя нового файла
            name_part, ext = os.path.splitext(ortho.filename)
            clean_name = name_part.replace("_cog", "").replace("_3857", "")
            new_filename = f"{clean_name}_3857_cog.tif"
            output_path = os.path.join(temp_dir, new_filename)

            # [FIX] Удаляем старый файл назначения, если он существует (решает 'Output dataset exists')
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    print(f"Removed existing target file: {output_path}")
                except Exception as e:
                    print(f"Warning: Could not remove target file: {e}")

            # 3. Выполняем gdalwarp (с флагом -overwrite)
            cmd = [
                "gdalwarp", 
                "-t_srs", "EPSG:3857",
                "-r", "bilinear",
                "-of", "COG",
                "-co", "COMPRESS=DEFLATE",
                "-co", "PREDICTOR=2",
                "-co", "NUM_THREADS=ALL_CPUS",
                "-overwrite",  # Важный флаг для предотвращения ошибок
                local_path, output_path
            ]

            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                print(f"GDAL Error: {process.stderr}")
                raise Exception(f"GDAL Warp Error: {process.stderr}")

            print("Reprojection finished.")

            # 4. Считываем новые границы
            new_bounds = self._get_bounds_from_gdalinfo(output_path)
            
            # 5. Загружаем новый файл в MinIO
            self.minio.client.fput_object(
                "orthophotos", 
                new_filename, 
                output_path, 
                content_type="image/tiff"
            )
            print(f"Uploaded new file: {new_filename}")

            # 6. Удаляем старый файл (опционально, сейчас удаляем)
            try:
                self.minio.delete_file(ortho.filename)
            except Exception as e:
                print(f"Could not delete old file from MinIO: {e}")

            # 7. Обновляем БД (имя файла, границы и CRS)
            update_data = {
                "filename": new_filename,
                "bounds": json.dumps(new_bounds),
                "crs": "EPSG:3857"
            }
            self.ortho_manager.update_ortho(ortho_id, update_data)

            # 8. Очистка локальных файлов
            if os.path.exists(local_path): os.remove(local_path)
            if os.path.exists(output_path): os.remove(output_path)

            return jsonify({
                "message": "Reprojection successful",
                "filename": new_filename,
                "crs": "EPSG:3857"
            }), 200

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


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
                "bounds": b,
                "crs": getattr(ortho, 'crs', None)
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

            if self.minio.client:
                orig_bucket = self.minio.bucket_name
                self.minio.bucket_name = "orthophotos"
                self.minio.delete_file(existing.filename)
                self.minio.bucket_name = orig_bucket

            self.ortho_manager.delete_ortho(ortho_id)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 7. Получить тайл (ПРОКСИ на TiTiler)
    # =========================================================================
    def get_ortho_tile(self, ortho_id, z, x, y):
        try:
            # 1. Получаем имя файла из БД
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Not found"}), 404

            # 2. Формируем URL к TiTiler (внутренняя сеть Docker)
            # TiTiler работает на порту 8000 внутри сети
            titiler_host = "http://titiler:8000"
            s3_url = f"s3://orthophotos/{ortho.filename}"
            
            # Параметры запроса
            params = {
                "url": s3_url,
                "rescale": "0,255"
            }
            
            tile_url = f"{titiler_host}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@1x"
            
            # 3. Делаем запрос к TiTiler (Backend-to-Backend)
            # Это обходит проблемы CORS, так как запрос идет внутри сервера
            resp = requests.get(tile_url, params=params)
            
            if resp.status_code != 200:
                print(f"TiTiler Error ({resp.status_code}): {resp.text}")
                return jsonify({"error": "TiTiler failed"}), resp.status_code

            # 4. Отдаем картинку клиенту
            response = make_response(resp.content)
            response.headers.set("Content-Type", "image/png")
            # Можно добавить кэширование
            response.headers.set("Cache-Control", "public, max-age=3600")
            return response

        except Exception as e:
            traceback.print_exc()
            # Возвращаем прозрачный пиксель при ошибке
            return self._tile_png_rgba_transparent()


    # =========================================================================
    # Вспомогательные функции GDAL (с определением МСК-05)
    # =========================================================================
    def _get_crs_from_gdalinfo(self, path):
        import json
        try:
            # Используем флаг -proj4 для более точного определения параметров
            process = subprocess.Popen(["gdalinfo", "-json", "-proj4", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, _ = process.communicate()
            data = json.loads(out)
            
            # Проверяем наличие информации о системе координат
            if "coordinateSystem" in data:
                cs = data["coordinateSystem"]
                wkt = cs.get("wkt", "")
                proj4 = cs.get("proj4", "")
                
                # 1. Проверяем стандартные коды EPSG
                if 'ID["EPSG",3857]' in wkt or "Pseudo-Mercator" in wkt:
                    return "EPSG:3857 (Google)"
                if 'ID["EPSG",4326]' in wkt:
                    return "EPSG:4326 (WGS84)"

                # 2. Определяем МСК-05 (Республика Дагестан) по уникальным параметрам
                # Центральный меридиан: 46.8916666667
                # Смещение по Y (False Northing): -4542821.516
                
                # Проверка по Proj4 (самая надежная)
                if "46.8916666667" in proj4 or "46.891667" in proj4:
                    return "MSK-05 (Dagestan)"
                
                # Проверка по WKT строке (если Proj4 нет)
                wkt_dump = json.dumps(cs)
                if "46.8916666667" in wkt_dump:
                    return "MSK-05 (Dagestan)"
                
                # Если ничего не нашли, но есть WKT - возвращаем тип
                if wkt and 'PROJCRS' in wkt:
                    return "Custom / Unknown Projection"

            return "Unknown"
        except Exception as e:
            print(f"Error detecting CRS: {e}")
            return "Unknown"

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