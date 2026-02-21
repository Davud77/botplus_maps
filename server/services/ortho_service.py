# services/ortho_service.py

import os
import uuid
import threading
import json
import traceback
import requests
from io import BytesIO
from PIL import Image
from osgeo import gdal
from models.ortho import Ortho
import config  # [NEW] Импортируем конфигурацию для доступа к .env

# Включаем исключения GDAL, чтобы отлавливать ошибки в try/except
gdal.UseExceptions()

class OrthoService:
    def __init__(self, db, ortho_manager, storage_service, gdal_service, task_service):
        self.db = db
        self.manager = ortho_manager
        self.storage = storage_service
        self.gdal = gdal_service
        self.tasks = task_service
        
        # [UPDATED] Берем путь из конфигурации (.env)
        self.temp_dir = getattr(config, 'TEMP_FOLDER', "data/temp/orthos")
        
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
                "preview_url": f"/api/orthophotos/{o.id}/preview" if getattr(o, 'preview_filename', None) else None,
                "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                "wgs84_bounds": getattr(o, 'wgs84_bounds', None),
                "crs": crs_val,
                "is_visible": getattr(o, 'is_visible', False),
                "is_cog": getattr(o, 'is_cog', False),
                "upload_date": str(o.upload_date) if hasattr(o, 'upload_date') else None
            })
        return results

    def _create_progress_callback(self, task_id, message="Обработка..."):
        """Создает функцию обратного вызова для нативного GDAL с честными процентами"""
        def progress_callback(complete, msg, cb_data):
            percent = int(complete * 100)
            # Обновляем статус, только если процент изменился, чтобы не спамить диск
            if getattr(progress_callback, "last_pct", -1) != percent:
                self.tasks.save_state(task_id, {
                    "status": "processing", 
                    "progress": percent, 
                    "message": f"{message} {percent}%"
                })
                progress_callback.last_pct = percent
            return 1 # 1 означает "продолжать работу"
        return progress_callback

    def start_upload_process(self, temp_file_path, filename):
        """Асинхронная обработка свежезагруженного файла"""
        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "message": "В очереди..."})

        def worker():
            logs = []
            preview_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 10, "message": "Сбор метаданных..."})
                logs.append(f"Начало фоновой обработки: {filename}")
                
                # 1. Сбор метаданных
                bounds = self.gdal.get_bounds(temp_file_path)
                crs = self.gdal.get_crs(temp_file_path)
                is_cog = self.gdal.check_is_cog(temp_file_path)
                footprint_wkt = self.gdal.get_footprint_wkt(temp_file_path)
                logs.append(f"Границы: {bounds}, CRS: {crs}, COG: {is_cog}")

                # 2. Генерация миниатюры
                self.tasks.save_state(task_id, {"status": "processing", "progress": 40, "message": "Генерация превью..."})
                preview_filename = f"{os.path.splitext(filename)[0]}_preview.png"
                preview_path = os.path.join(self.temp_dir, preview_filename)
                has_preview = False
                
                try:
                    # Нативный GDAL Translate для превью
                    translate_options = gdal.TranslateOptions(
                        format="PNG",
                        width=400,
                        height=0, # Вычислить пропорционально
                        resampleAlg="nearest"
                    )
                    ds = gdal.Translate(preview_path, temp_file_path, options=translate_options)
                    ds = None # Закрываем датасет, чтобы сбросить буфер на диск
                    has_preview = True
                    logs.append("Миниатюра успешно сгенерирована.")
                except Exception as e:
                    logs.append(f"Внимание: Не удалось создать превью: {e}")

                # 3. Загрузка в MinIO
                self.tasks.save_state(task_id, {"status": "processing", "progress": 70, "message": "Отправка в хранилище..."})
                self.storage.upload_file(filename, temp_file_path)
                logs.append("Основной файл загружен в MinIO")
                
                if has_preview:
                    self.storage.upload_file(preview_filename, preview_path)
                    logs.append("Миниатюра загружена в MinIO")

                # 4. Запись в БД
                self.tasks.save_state(task_id, {"status": "processing", "progress": 90, "message": "Сохранение в БД..."})
                ortho_obj = Ortho(
                    filename=filename, 
                    bounds=json.dumps(bounds),
                    url=None,
                    is_visible=False,
                    crs=crs,
                    is_cog=is_cog,             
                    geometry_wkt=footprint_wkt,
                    preview_filename=preview_filename if has_preview else None
                )
                
                ortho_id = self.manager.insert_ortho(ortho_obj)
                logs.append(f"Успех. Запись добавлена в БД (ID: {ortho_id})")
                
                self.tasks.save_state(task_id, {
                    "status": "success", 
                    "progress": 100, 
                    "message": "Готово",
                    "logs": logs
                })

            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "progress": 0, "error": str(e), "logs": logs})
            finally:
                if os.path.exists(temp_file_path):
                    try: os.remove(temp_file_path)
                    except: pass
                if preview_path and os.path.exists(preview_path):
                    try: os.remove(preview_path)
                    except: pass

        threading.Thread(target=worker).start()
        return task_id

    def start_cog_process(self, ortho_id):
        """Оптимизация файла в Cloud Optimized GeoTIFF (COG)"""
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, ortho.filename)
            cog_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Скачивание из S3..."})
                self.storage.download_file(ortho.filename, local_path)

                name_part, ext = os.path.splitext(ortho.filename)
                new_filename = f"{name_part}_v2.tif" if "_cog" in name_part else f"{name_part}_cog.tif"
                cog_path = os.path.join(self.temp_dir, new_filename)

                # Нативный GDAL с коллбэком прогресса
                cb = self._create_progress_callback(task_id, message="Конвертация в COG...")
                
                translate_options = gdal.TranslateOptions(
                    format="COG",
                    creationOptions=[
                        "BIGTIFF=IF_NEEDED",
                        "COMPRESS=NONE",
                        "NUM_THREADS=ALL_CPUS",
                        "SPARSE_OK=TRUE",
                        "OVERVIEWS=IGNORE_EXISTING"
                    ],
                    callback=cb
                )

                ds = gdal.Translate(cog_path, local_path, options=translate_options)
                ds = None # Завершаем запись файла
                
                self.tasks.save_state(task_id, {"status": "processing", "progress": 95, "message": "Сохранение метаданных..."})
                
                # Обновляем метаданные и загружаем результат
                bounds = self.gdal.get_bounds(cog_path)
                crs = self.gdal.get_crs(cog_path)
                is_cog = self.gdal.check_is_cog(cog_path)
                geom_wkt = self.gdal.get_footprint_wkt(cog_path)

                self.storage.upload_file(new_filename, cog_path)

                new_ortho = Ortho(
                    filename=new_filename, 
                    bounds=json.dumps(bounds), 
                    url=None, 
                    crs=crs, 
                    is_visible=False,
                    is_cog=is_cog,          
                    geometry_wkt=geom_wkt,
                    preview_filename=getattr(ortho, 'preview_filename', None)
                )
                self.manager.insert_ortho(new_ortho)

                self.tasks.save_state(task_id, {"status": "success", "progress": 100, "message": "Оптимизация завершена!"})
            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "error": str(e)})
            finally:
                if os.path.exists(local_path):
                    try: os.remove(local_path)
                    except: pass
                if cog_path and os.path.exists(cog_path):
                    try: os.remove(cog_path)
                    except: pass

        threading.Thread(target=worker).start()
        return task_id

    def start_reproject_process(self, ortho_id):
        """Перепроецирование в Web Mercator (EPSG:3857) с сохранением COG"""
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, ortho.filename)
            output_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Скачивание из S3..."})
                self.storage.download_file(ortho.filename, local_path)
                
                name_part, ext = os.path.splitext(ortho.filename)
                clean_name = name_part.replace("_cog", "").replace("_3857", "")
                new_filename = f"{clean_name}_3857_cog.tif"
                output_path = os.path.join(self.temp_dir, new_filename)

                # Нативный GDAL Warp с коллбэком прогресса
                cb = self._create_progress_callback(task_id, message="Перепроецирование в 3857...")

                warp_options = gdal.WarpOptions(
                    dstSRS="EPSG:3857",
                    resampleAlg="cubic",
                    format="COG",
                    creationOptions=[
                        "BIGTIFF=IF_NEEDED",
                        "COMPRESS=NONE",
                        "NUM_THREADS=ALL_CPUS",
                        "SPARSE_OK=TRUE"
                    ],
                    callback=cb
                )

                ds = gdal.Warp(output_path, local_path, options=warp_options)
                ds = None # Завершаем запись
                
                self.tasks.save_state(task_id, {"status": "processing", "progress": 95, "message": "Сохранение метаданных..."})

                # Забираем новые метаданные
                new_bounds = self.gdal.get_bounds(output_path)
                is_cog = self.gdal.check_is_cog(output_path)
                geom_wkt = self.gdal.get_footprint_wkt(output_path)

                self.storage.upload_file(new_filename, output_path)

                new_ortho = Ortho(
                    filename=new_filename, 
                    bounds=json.dumps(new_bounds),
                    url=None, 
                    crs="EPSG:3857", 
                    is_visible=False,
                    is_cog=is_cog,         
                    geometry_wkt=geom_wkt,
                    preview_filename=getattr(ortho, 'preview_filename', None)
                )
                self.manager.insert_ortho(new_ortho)

                self.tasks.save_state(task_id, {"status": "success", "progress": 100, "message": "Конвертация успешно завершена"})
            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "error": str(e)})
            finally:
                if os.path.exists(local_path):
                    try: os.remove(local_path)
                    except: pass
                if output_path and os.path.exists(output_path):
                    try: os.remove(output_path)
                    except: pass

        threading.Thread(target=worker).start()
        return task_id

    def start_preview_process(self, ortho_id):
        """Ручная генерация превью для файла, у которого его нет"""
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        task_id = str(uuid.uuid4())
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, ortho.filename)
            preview_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 10, "message": "Скачивание исходника..."})
                self.storage.download_file(ortho.filename, local_path)
                
                name_part, ext = os.path.splitext(ortho.filename)
                preview_filename = f"{name_part}_preview.png"
                preview_path = os.path.join(self.temp_dir, preview_filename)

                cb = self._create_progress_callback(task_id, message="Генерация превью...")

                translate_options = gdal.TranslateOptions(
                    format="PNG",
                    width=400,
                    height=0,
                    resampleAlg="nearest",
                    callback=cb
                )
                
                ds = gdal.Translate(preview_path, local_path, options=translate_options)
                ds = None

                self.tasks.save_state(task_id, {"status": "processing", "progress": 90, "message": "Загрузка превью в хранилище..."})
                self.storage.upload_file(preview_filename, preview_path)
                
                self.manager.update_ortho(ortho_id, {"preview_filename": preview_filename})
                
                self.tasks.save_state(task_id, {"status": "success", "progress": 100, "message": "Превью сгенерировано"})
            except Exception as e:
                traceback.print_exc()
                self.tasks.save_state(task_id, {"status": "error", "error": str(e)})
            finally:
                if os.path.exists(local_path):
                    try: os.remove(local_path)
                    except: pass
                if preview_path and os.path.exists(preview_path):
                    try: os.remove(preview_path)
                    except: pass

        threading.Thread(target=worker).start()
        return task_id

    def proxy_tile(self, ortho_id, z, x, y):
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        # [UPDATED] Берем настройки внутренних сервисов из конфигурации (.env)
        titiler_host = getattr(config, 'TITILER_INTERNAL_URL', "http://titiler:80")
        minio_endpoint = getattr(config, 'MINIO_ENDPOINT', "minio:9000")
        bucket_name = getattr(config, 'MINIO_ORTHO_BUCKET', "orthophotos")
        
        s3_url = f"http://{minio_endpoint}/{bucket_name}/{ortho.filename}"
        
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
            
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()