# services/ortho_service.py

import os
import uuid
import threading
import json
import traceback
import requests
from io import BytesIO
from PIL import Image
from models.ortho import Ortho

# Размер чанка для чтения (8MB)
CHUNK_SIZE = 8192 * 1024

class OrthoService:
    def __init__(self, db, ortho_manager, storage_service, gdal_service, task_service):
        self.db = db
        self.manager = ortho_manager
        self.storage = storage_service
        self.gdal = gdal_service
        self.tasks = task_service
        self.temp_dir = "data/temp/orthos"
        
        if not os.path.exists(self.temp_dir):
            try: os.makedirs(self.temp_dir, exist_ok=True)
            except: pass

    def get_all(self):
        orthos = self.manager.get_all_orthos()
        results = []
        for o in orthos:
            b = None
            if o.bounds:
                try: b = json.loads(o.bounds)
                except: pass 
            
            crs_val = getattr(o, 'crs', None)
            if not crs_val and o.filename and "_3857" in o.filename:
                crs_val = "EPSG:3857"

            results.append({
                "id": o.id,
                "filename": o.filename,
                "url": f"/api/orthophotos/{o.id}/download",
                "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                "crs": crs_val,
                "is_visible": getattr(o, 'is_visible', False),
                "upload_date": str(o.upload_date) if hasattr(o, 'upload_date') else None
            })
        return results

    def handle_upload(self, files):
        logs = []
        successful = []
        failed = []

        for file in files:
            filename = file.filename
            input_path = os.path.join(self.temp_dir, filename)
            try:
                logs.append(f"Начало загрузки: {filename}")
                
                # Потоковая запись файла на диск
                with open(input_path, 'wb') as f:
                    while True:
                        chunk = file.stream.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                
                logs.append("Файл сохранен на диск (streaming save).")
                
                bounds = self.gdal.get_bounds(input_path)
                crs = self.gdal.get_crs(input_path)
                logs.append(f"Границы: {bounds}, CRS: {crs}")

                ortho_obj = Ortho(
                    filename=filename, 
                    bounds=json.dumps(bounds),
                    url=None,
                    is_visible=False,
                    crs=crs
                )
                ortho_id = self.manager.insert_ortho(ortho_obj)
                
                if self.storage.upload_file(filename, input_path):
                    logs.append("Файл загружен в MinIO")
                    if os.path.exists(input_path): os.remove(input_path)
                else:
                    logs.append("Ошибка: MinIO недоступен")
                
                successful.append(filename)
            except Exception as e:
                logs.append(f"Ошибка: {e}")
                failed.append(filename)
                if os.path.exists(input_path):
                    try: os.remove(input_path)
                    except: pass
        
        return successful, failed, logs

    def start_cog_process(self, ortho_id):
        """
        Конвертация в COG.
        Настройки приведены в соответствие с GeoTiff3_COG.py:
        - BIGTIFF=IF_NEEDED (Исправляет ошибку размера)
        - COMPRESS=NONE (Отключает сжатие)
        - RESAMPLING=CUBIC (Улучшает качество)
        """
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            try:
                local_path = os.path.join(self.temp_dir, ortho.filename)
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Downloading..."})
                
                self.storage.download_file(ortho.filename, local_path)
                self.tasks.save_state(task_id, {"status": "processing", "progress": 10, "message": "Converting..."})

                name_part, ext = os.path.splitext(ortho.filename)
                new_filename = f"{name_part}_v2.tif" if "_cog" in name_part else f"{name_part}_cog.tif"
                cog_path = os.path.join(self.temp_dir, new_filename)

                # [FIX] Настройки из твоего скрипта GeoTiff3_COG.py
                cmd = [
                    "gdal_translate", local_path, cog_path,
                    "-of", "COG", 
                    "-co", "BIGTIFF=IF_NEEDED",     # <-- РЕШАЕТ ПРОБЛЕМУ "Maximum TIFF file size exceeded"
                    "-co", "COMPRESS=NONE",         # <-- Отключаем сжатие, как просил
                    "-co", "NUM_THREADS=ALL_CPUS", 
                    "-co", "OVERVIEWS=IGNORE_EXISTING",
                    "-co", "RESAMPLING=CUBIC",      # <-- Более качественное сглаживание
                    "-co", "SPARSE_OK=TRUE"         # <-- Экономит место, если есть пустые области
                ]

                def on_success():
                    self.storage.upload_file(new_filename, cog_path)
                    bounds = self.gdal.get_bounds(cog_path)
                    crs = self.gdal.get_crs(cog_path)
                    new_ortho = Ortho(filename=new_filename, bounds=json.dumps(bounds), url=None, crs=crs, is_visible=False)
                    new_id = self.manager.insert_ortho(new_ortho)
                    return {"new_id": new_id, "new_filename": new_filename}

                self.gdal.run_background_process(cmd, local_path, cog_path, task_id, self.tasks, on_success, start_percent=10)
            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "error": str(e)})

        threading.Thread(target=worker).start()
        return task_id

    def start_reproject_process(self, ortho_id):
        """
        Перепроецирование в Web Mercator.
        Также применяем настройки BIGTIFF и CUBIC.
        """
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            try:
                local_path = os.path.join(self.temp_dir, ortho.filename)
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Downloading..."})
                self.storage.download_file(ortho.filename, local_path)
                
                self.tasks.save_state(task_id, {"status": "processing", "progress": 10, "message": "Reprojecting..."})
                
                name_part, ext = os.path.splitext(ortho.filename)
                clean_name = name_part.replace("_cog", "").replace("_3857", "")
                new_filename = f"{clean_name}_3857_cog.tif"
                output_path = os.path.join(self.temp_dir, new_filename)

                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except: pass

                # [FIX] Настройки GDAL Warp для больших файлов
                cmd = [
                    "gdalwarp", 
                    "-t_srs", "EPSG:3857", 
                    "-r", "cubic",                  # <-- Используем cubic вместо билинейного (лучше качество)
                    "-of", "COG",
                    "-co", "BIGTIFF=IF_NEEDED",     # <-- РЕШАЕТ ПРОБЛЕМУ
                    "-co", "COMPRESS=NONE",         # <-- Без сжатия
                    "-co", "NUM_THREADS=ALL_CPUS",
                    "-co", "SPARSE_OK=TRUE",
                    "-overwrite", local_path, output_path
                ]

                def on_success():
                    self.storage.upload_file(new_filename, output_path)
                    new_bounds = self.gdal.get_bounds(output_path)
                    new_ortho = Ortho(
                        filename=new_filename, bounds=json.dumps(new_bounds),
                        url=None, crs="EPSG:3857", is_visible=False
                    )
                    new_id = self.manager.insert_ortho(new_ortho)
                    return {"new_id": new_id, "filename": new_filename}

                self.gdal.run_background_process(cmd, local_path, output_path, task_id, self.tasks, on_success, start_percent=10)
            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "error": str(e)})

        threading.Thread(target=worker).start()
        return task_id

    def proxy_tile(self, ortho_id, z, x, y):
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        titiler_host = "http://titiler:80"
        s3_url = f"http://minio:9000/orthophotos/{ortho.filename}"
        
        try:
            resp = requests.get(
                f"{titiler_host}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}",
                params={"url": s3_url, "rescale": "0,255"},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.content
        except:
            pass
            
        # Возврат прозрачного PNG при ошибке
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()