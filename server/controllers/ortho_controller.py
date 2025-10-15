# ./backend/controllers/ortho_controller.py

from flask import Blueprint, jsonify, request, make_response
from managers.ortho_manager import OrthoManager
from database import Database
from models.ortho import Ortho
from storage import LocalStorage
import config
import json
import subprocess
import os
import re
import sys
from io import BytesIO
from PIL import Image

ortho_blueprint = Blueprint("ortho", __name__)

class OrthoController:
    def __init__(self):
        self.db = Database()
        self.ortho_manager = OrthoManager(self.db)
        self.storage = LocalStorage(config.ORTHO_FOLDER)

    @staticmethod
    def register_routes(blueprint):
        controller = OrthoController()

        # Список орто
        blueprint.add_url_rule("/orthophotos", 
                               view_func=controller.get_orthophotos, 
                               methods=["GET"])
        
        # Загрузка орто (приводим к EPSG:3857), делаем preview, генерируем тайлы
        blueprint.add_url_rule("/upload_ortho", 
                               view_func=controller.upload_ortho, 
                               methods=["POST"])
        
        # Получить информацию об одном орто
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.get_ortho, 
                               methods=["GET"])
        
        # Скачать превью
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/download", 
                               view_func=controller.download_ortho_file, 
                               methods=["GET"])
        
        # Обновить
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.update_ortho, 
                               methods=["PUT"])
        
        # Удалить
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", 
                               view_func=controller.delete_ortho, 
                               methods=["DELETE"])

        # Получить предсгенерированный тайл (PNG)
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
                b = json.loads(o.bounds) if o.bounds else None
                item = {
                    "id": o.id,
                    "filename": o.filename,  
                    "url": f"https://api.botplus.ru/orthophotos/{o.id}/download",
                    "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                }
                results.append(item)
            return jsonify(results), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 2. Загрузка GeoTIFF: приводим к EPSG:3857, делаем preview, генерируем тайлы
    # =========================================================================
    def upload_ortho(self):
        uploaded_files = request.files.getlist("files")
        successful_uploads = []
        failed_uploads = []
        logs = []  # Для сбора детальных логов

        if not uploaded_files:
            logs.append("Файлы не были переданы.")
            return jsonify({
                "message": "Нет переданных файлов.",
                "successful_uploads": [],
                "failed_uploads": [],
                "logs": logs
            }), 400

        for file in uploaded_files:
            original_filename = file.filename
            try:
                logs.append(f"Начинаем обработку файла: {original_filename}")
                base_name, ext = os.path.splitext(original_filename)

                # 1. Сохраняем во временный файл
                input_path = os.path.join(config.ORTHO_FOLDER, original_filename)
                file.save(input_path)
                if not os.path.exists(input_path):
                    raise FileNotFoundError(f"Не удалось сохранить файл: {input_path}")
                logs.append(f"Файл сохранён во временное место: {input_path}")

                # 2. Проверяем проекцию => если не EPSG:3857, warp
                current_crs = self._get_crs_from_gdalinfo(input_path)
                logs.append(f"Текущая проекция файла: {current_crs}")
                final_tiff_filename = f"{base_name}_3857.tif"
                final_tiff_path = os.path.join(config.ORTHO_FOLDER, final_tiff_filename)

                if current_crs != "EPSG:3857":
                    logs.append("Выполняем gdalwarp для перевода проекции в EPSG:3857")
                    self._warp_to_mercator(input_path, final_tiff_path)
                    os.remove(input_path)
                    logs.append(f"Файл {original_filename} преобразован и сохранён как {final_tiff_filename}")
                else:
                    os.rename(input_path, final_tiff_path)
                    logs.append(f"Файл уже в EPSG:3857, переименован в {final_tiff_filename}")

                # 3. Генерируем превью
                preview_filename = f"{base_name}_3857_preview.png"
                preview_path = os.path.join(config.ORTHO_FOLDER, preview_filename)
                logs.append(f"Генерация превью: {preview_filename}")
                self._create_preview(final_tiff_path, preview_path)

                # 4. Считываем bounds
                logs.append("Считываем границы (bounds) c gdalinfo")
                bounds = self._get_bounds_from_gdalinfo(final_tiff_path)

                # 5. Сохраняем запись в БД
                ortho_obj = Ortho(
                    filename=preview_filename,
                    bounds=json.dumps(bounds)
                )
                ortho_id = self.ortho_manager.insert_ortho(ortho_obj)
                logs.append(f"Создана запись в базе данных ID={ortho_id}")

                # 6. Генерируем тайлы
                tiles_folder = os.path.join(config.TILES_FOLDER, str(ortho_id))
                os.makedirs(tiles_folder, exist_ok=True)
                logs.append(f"Начинаем генерацию тайлов в папку: {tiles_folder}")
                self._generate_tiles(final_tiff_path, tiles_folder, logs)
                logs.append(f"Тайлы успешно сгенерированы для Ortho ID={ortho_id}")

                successful_uploads.append(original_filename)

            except Exception as err:
                error_msg = f"Ошибка при обработке файла {original_filename}: {err}"
                print(error_msg)
                logs.append(error_msg)
                failed_uploads.append(original_filename)

        return jsonify({
            "message": "Загрузка завершена (EPSG:3857, preview, tiles).",
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "logs": logs
        }), 200


    # =========================================================================
    # 3. Получить информацию об орто
    # =========================================================================
    def get_ortho(self, ortho_id):
        try:
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Orthophoto not found"}), 404

            bounds = json.loads(ortho.bounds) if ortho.bounds else None
            result = {
                "id": ortho.id,
                "filename": ortho.filename,
                "url": f"https://api.botplus.ru/orthophotos/{ortho.id}/download",
                "bounds": bounds
            }
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 4. Скачать preview-файл (PNG)
    # =========================================================================
    def download_ortho_file(self, ortho_id):
        try:
            ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not ortho:
                return jsonify({"error": "Orthophoto not found"}), 404

            return self.storage.send_local_file(ortho.filename, mimetype="image/png")
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 5. Обновить
    # =========================================================================
    def update_ortho(self, ortho_id):
        try:
            data = request.json
            existing = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not existing:
                return jsonify({"error": "Orthophoto not found"}), 404

            updated_fields = {}
            for field in ["filename", "bounds"]:
                if field in data:
                    if field == "bounds" and isinstance(data[field], dict):
                        updated_fields[field] = json.dumps(data[field])
                    else:
                        updated_fields[field] = data[field]

            self.ortho_manager.update_ortho(ortho_id, updated_fields)
            return jsonify({"status": "success", "message": "Orthophoto updated"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 6. Удалить
    # =========================================================================
    def delete_ortho(self, ortho_id):
        try:
            existing = self.ortho_manager.get_ortho_by_id(ortho_id)
            if not existing:
                return jsonify({"error": "Orthophoto not found"}), 404

            # Удаляем превью
            file_path = os.path.join(config.ORTHO_FOLDER, existing.filename)
            if os.path.exists(file_path):
                os.remove(file_path)

            # Удаляем тайловую папку
            tiles_path = os.path.join(config.TILES_FOLDER, str(ortho_id))
            if os.path.exists(tiles_path):
                import shutil
                shutil.rmtree(tiles_path)

            # Удаляем запись из БД
            self.ortho_manager.delete_ortho(ortho_id)

            return jsonify({"status": "success", "message": "Orthophoto deleted"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # =========================================================================
    # 7. Получить тайл (PNG)
    # =========================================================================
    def get_ortho_tile(self, ortho_id, z, x, y):
        try:
            tile_path = os.path.join(config.TILES_FOLDER, str(ortho_id), str(z), str(x), f"{y}.png")
            if os.path.exists(tile_path):
                return self.storage.send_local_file(tile_path, mimetype="image/png")
            else:
                return self._tile_png_rgba_transparent()
        except Exception as e:
            print(f"Ошибка при выдаче тайла: {e}")
            return self._tile_png_rgba_transparent()


    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================================
    def _warp_to_mercator(self, input_path, output_path):
        print(f"[Warp] Запуск gdalwarp для файла: {input_path}")
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
        print(f"[Warp] Файл успешно переведён в EPSG:3857: {output_path}")

    def _create_preview(self, input_path, output_path):
        print(f"[Preview] Создание превью PNG: {output_path}")
        cmd = [
            "gdal_translate",
            "-of", "PNG",
            "-outsize", "2048", "0",
            input_path,
            output_path
        ]
        subprocess.check_call(cmd)
        print(f"[Preview] Превью сохранено: {output_path}")

    def _generate_tiles(self, tiff_path, dest_folder, logs):
        """
        Генерируем тайлы через "python -m osgeo_utils.gdal2tiles"
        (начиная с GDAL 3.3, gdal2tiles лежит в osgeo_utils).

        Включаем многопроцессность (--processes) с числом потоков = количеству ядер,
        чтобы использовать 100% ресурсов CPU. 
        Добавляем --verbose для детального вывода.
        Читаем вывод построчно, логируем в реальном времени.
        Диапазон зумов 0-20.
        """
        import multiprocessing
        nproc = multiprocessing.cpu_count()  # все CPU

        start_msg = f"[Tiles] Старт генерации тайлов для: {tiff_path}"
        print(start_msg)
        logs.append(start_msg)

        cmd = [
            sys.executable,
            "-m", "osgeo_utils.gdal2tiles",
            "--profile=mercator",
            "--xyz",
            "--verbose",
            "--processes", str(nproc),
            "-z", "0-20",
            tiff_path,
            dest_folder
        ]
        cmd_msg = f"[Tiles] Команда: {' '.join(cmd)}"
        print(cmd_msg)
        logs.append(cmd_msg)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Читаем stdout построчно, логируем прогресс
        while True:
            line = process.stdout.readline()
            if not line:
                break
            line_stripped = line.strip()
            print(f"[Tiles - stdout] {line_stripped}")
            logs.append(f"[Tiles - stdout] {line_stripped}")

        # Теперь считываем оставшиеся строки из stderr (если есть)
        while True:
            line_err = process.stderr.readline()
            if not line_err:
                break
            line_err_stripped = line_err.strip()
            print(f"[Tiles - stderr] {line_err_stripped}")
            logs.append(f"[Tiles - stderr] {line_err_stripped}")

        retcode = process.wait()
        if retcode != 0:
            error_msg = f"[Tiles] gdal2tiles завершился с ошибкой (код {retcode})."
            print(error_msg)
            logs.append(error_msg)
            raise Exception(error_msg)
        else:
            done_msg = "[Tiles] Генерация тайлов успешно завершена."
            print(done_msg)
            logs.append(done_msg)

    def _get_crs_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(
            ["gdalinfo", "-json", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = process.communicate()
        if process.returncode != 0:
            raise Exception(f"Ошибка gdalinfo: {err}")

        data = json.loads(out)
        coord_system = data.get("coordinateSystem", {})
        cs_data = coord_system.get("data", {})
        epsg_code = cs_data.get("code")
        if epsg_code:
            return f"EPSG:{epsg_code}"

        wkt = coord_system.get("wkt", "")
        match = re.search(r'AUTHORITY$$"EPSG","(\d+)"$$', wkt)
        if match:
            return f"EPSG:{match.group(1)}"
        return "UNKNOWN"

    def _get_bounds_from_gdalinfo(self, path):
        import json
        process = subprocess.Popen(
            ["gdalinfo", "-json", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = process.communicate()
        if process.returncode != 0:
            raise Exception(f"gdalinfo error: {err}")

        data = json.loads(out)
        corner_coords = data.get("cornerCoordinates")
        if not corner_coords:
            raise Exception("Не найдены cornerCoordinates в gdalinfo -json.")

        coords_list = [
            corner_coords["upperLeft"],
            corner_coords["lowerLeft"],
            corner_coords["upperRight"],
            corner_coords["lowerRight"]
        ]
        xs = [c[0] for c in coords_list]
        ys = [c[1] for c in coords_list]

        west = min(xs)
        east = max(xs)
        south = min(ys)
        north = max(ys)
        return {"north": north, "south": south, "east": east, "west": west}

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