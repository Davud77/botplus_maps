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
from werkzeug.utils import secure_filename
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

    def catalog_projection(self,definition):
        from services.map_settings import ensure_projection
        with self.db.cursor(write=True) as cur:return ensure_projection(cur,definition)['id']

    def get_all(self):
        orthos = self.manager.get_all_orthos()
        with self.db.cursor() as cur:
            cur.execute('SELECT id,name FROM coordinate_systems')
            projection_names={row['id']:row['name'] for row in cur.fetchall()}
            cur.execute("""SELECT ortho_id FROM import_assets WHERE asset ? 'display'
                UNION ALL SELECT ortho_id FROM raster_sources s WHERE asset ? 'display'
                AND NOT EXISTS(SELECT 1 FROM import_assets a WHERE a.ortho_id=s.ortho_id)""")
            display_ready={row['ortho_id'] for row in cur.fetchall()}
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
                "display_name": getattr(o,"display_name",None) or o.filename,
                "url": f"/api/orthophotos/{o.id}/download",
                "preview_url": f"/api/orthophotos/{o.id}/preview" if getattr(o, 'preview_filename', None) else None,
                "bounds": b if b else {"north": 0, "south": 0, "east": 0, "west": 0},
                "wgs84_bounds": getattr(o, 'wgs84_bounds', None),
                "crs": crs_val,
                "crs_name": projection_names.get(crs_val,crs_val),
                "is_visible": getattr(o, 'is_visible', False),
                "is_cog": getattr(o, 'is_cog', False),
                "display_ready": o.id in display_ready,
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
                crs = self.catalog_projection(self.gdal.get_crs(temp_file_path))
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

                # 3. Сохранение на подключённом диске
                self.tasks.save_state(task_id, {"status": "processing", "progress": 70, "message": "Отправка в хранилище..."})
                self.storage.upload_file(filename, temp_file_path)
                logs.append("Основной файл сохранён на диске")

                if has_preview:
                    self.storage.upload_file(preview_filename, preview_path)
                    logs.append("Миниатюра сохранена на диске")

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

        if not getattr(self,'worker_task_id',None):
            from flask import g
            import import_jobs
            return str(import_jobs.enqueue_operation(g.current_user_id,'cog','COG: '+ortho.filename,{'ortho_id':ortho_id},self.db)['id'])
        task_id = self.worker_task_id
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, "source.tif")
            cog_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Подготовка рабочего файла..."})
                import import_jobs, shutil
                asset=import_jobs.asset_record(ortho_id,self.db)
                if asset:shutil.copyfile(import_jobs.asset_path(asset),local_path)
                else:self.storage.download_file(ortho.filename, local_path)

                name_part, ext = os.path.splitext(secure_filename(ortho.filename) or "orthophoto.tif")
                new_filename = f"{name_part}_{task_id[:8]}_cog.tif"
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
                crs = self.catalog_projection(self.gdal.get_crs(cog_path))
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

        worker()
        return task_id

    def start_reproject_process(self, ortho_id, target_crs="EPSG:3857"):
        """Create a reprojected copy in a selected catalog CRS."""
        with self.db.cursor() as cur:
            cur.execute('SELECT * FROM coordinate_systems WHERE id=%s',(target_crs,))
            target=cur.fetchone()
        if not target or not target['definition']:raise ValueError('Для целевой проекции не задано определение.')
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        if not getattr(self,'worker_task_id',None):
            from flask import g
            import import_jobs
            return str(import_jobs.enqueue_operation(g.current_user_id,'reproject','Смена системы координат: '+ortho.filename,{'ortho_id':ortho_id,'target_crs':target_crs},self.db)['id'])
        task_id = self.worker_task_id
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, "source.tif")
            output_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 2, "message": "Подготовка рабочего файла..."})
                import import_jobs, shutil
                asset=import_jobs.asset_record(ortho_id,self.db)
                if asset:shutil.copyfile(import_jobs.asset_path(asset),local_path)
                else:self.storage.download_file(ortho.filename, local_path)

                name_part, ext = os.path.splitext(secure_filename(ortho.filename) or "orthophoto.tif")
                clean_name = name_part.replace("_cog", "").replace("_3857", "")
                new_filename = f"{clean_name}_{task_id[:8]}_reprojected.tif"
                output_path = os.path.join(self.temp_dir, new_filename)

                # Нативный GDAL Warp с коллбэком прогресса
                cb = self._create_progress_callback(task_id, message="Перепроецирование: "+target["name"])

                with self.db.cursor() as cur:
                    cur.execute('SELECT definition FROM coordinate_systems WHERE id=%s',(ortho.crs,))
                    source_projection=cur.fetchone()
                source_options={'srcSRS':source_projection['definition']} if source_projection and source_projection['definition'] else {}
                warp_options = gdal.WarpOptions(
                    **source_options,
                    dstSRS=target["definition"],
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
                    crs=target_crs,
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

        worker()
        return task_id

    def start_preview_process(self, ortho_id):
        """Ручная генерация превью для файла, у которого его нет"""
        ortho = self.manager.get_ortho_by_id(ortho_id)
        if not ortho: return None

        if not getattr(self,'worker_task_id',None):
            from flask import g
            import import_jobs
            return str(import_jobs.enqueue_operation(g.current_user_id,'preview','Создание превью: '+ortho.filename,{'ortho_id':ortho_id},self.db)['id'])
        task_id = self.worker_task_id
        self.tasks.save_state(task_id, {"status": "pending", "progress": 0, "filename": ortho.filename})

        def worker():
            local_path = os.path.join(self.temp_dir, "source.tif")
            preview_path = None
            try:
                self.tasks.save_state(task_id, {"status": "processing", "progress": 10, "message": "Скачивание исходника..."})
                import import_jobs, shutil
                asset=import_jobs.asset_record(ortho_id,self.db)
                if asset:shutil.copyfile(import_jobs.asset_path(asset),local_path)
                else:self.storage.download_file(ortho.filename, local_path)

                name_part, ext = os.path.splitext(secure_filename(ortho.filename) or "orthophoto.tif")
                preview_filename = f"{name_part}_{task_id[:8]}_preview.png"
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

        worker()
        return task_id

    def proxy_tile(self, ortho_id, z, x, y, scale=1, image_format='png', metrics=None):
        import time
        from pathlib import Path
        import import_jobs
        from flask import abort, g, has_request_context
        from raster_cache import configured_cache, RasterCache
        from display_jobs import base_asset, display_path
        if image_format not in {'png','webp'} or scale not in (1,2) or z<0 or z>24 or x<0 or y<0 or x>=2**z or y>=2**z:abort(404)
        started=time.perf_counter()
        ortho=self.manager.get_ortho_by_id(ortho_id)
        if not ortho:return None
        asset=import_jobs.asset_record(ortho_id,self.db)
        try:
            path=import_jobs.asset_path(asset) if asset else Path(self.storage.get_local_file_path(ortho.filename))
            descriptor=base_asset(asset) if asset else {'legacy':str(path),'fingerprint':import_jobs.fingerprint(path)}
            display=display_path(asset,z,scale) if asset and image_format=='webp' else None
            if display:
                path=display;descriptor={'native':descriptor,'display':asset['display']}
        except (ValueError,OSError):abort(409,description='Источник изменён или недоступен. Проверьте импорт и подключённый диск.')
        resolved=time.perf_counter();render_seconds=0
        def fetch_raster(output_format):
            nonlocal render_seconds
            begin=time.perf_counter()
            host=getattr(config,'TITILER_INTERNAL_URL','http://titiler:80')
            suffix='@2x' if scale==2 else ''
            try:
                response=requests.get(f'{host}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}{suffix}.{output_format}',params={'url':str(path),'rescale':'0,255'},timeout=(3,30))
                if response.status_code!=200:return None
                # Never publish a cached result if the source changed during GDAL.
                if asset:import_jobs.asset_path(asset)
                elif import_jobs.fingerprint(path)!=descriptor['fingerprint']:raise ValueError('Source changed')
                if display and display_path(asset,z,scale)!=display:raise ValueError('Display product changed')
                return response.content
            except requests.RequestException:return None
            except (ValueError,OSError):abort(409,description='Источник изменился во время чтения.')
            finally:render_seconds=time.perf_counter()-begin
        def render():
            if image_format=='png':return fetch_raster('png')
            from io import BytesIO
            from PIL import Image
            # Reuse existing PNG tiles without nested shard locks. A miss renders
            # once under the WebP key's lock; sources are still checked above.
            try:cached=configured_cache().lookup(RasterCache.key(descriptor,z,x,y,scale))
            except OSError:cached=None
            try:
                if cached:
                    image=Image.open(BytesIO(cached[0]))
                else:
                    from raster_codec import decode_npy
                    raw=fetch_raster('npy')
                    if not raw:return None
                    image=decode_npy(raw,256*scale)
                with image:
                    output=BytesIO()
                    image.save(output,format='WEBP',quality=90,method=2,exact=True)
                    return output.getvalue()
            except (OSError,ValueError):return None
        try:
            content,state=configured_cache().get(RasterCache.key(descriptor,z,x,y,scale,image_format),render,extension=image_format)
        except TimeoutError:abort(503,description='Сервер тайлов занят. Повторите запрос.')
        except OSError:
            # Cache storage is optional; the source still must pass validation.
            content=render();state='BYPASS'
        timing=f'source;dur={(resolved-started)*1000:.2f}, render;dur={render_seconds*1000:.2f}, total;dur={(time.perf_counter()-started)*1000:.2f}'
        if metrics is not None:metrics.update(cache=state,server_timing=timing)
        if has_request_context():
            g.raster_cache=state
            g.raster_server_timing=timing
        return content
