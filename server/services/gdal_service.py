# server/services/gdal_service.py
import subprocess
import json
import os
import time
import traceback
from osgeo import gdal, osr, ogr  # Библиотеки для работы с геометрией и метаданными

class GdalService:
    
    @staticmethod
    def get_crs(path):
        """Определяет проекцию (МСК-05, Google, WGS84)"""
        try:
            process = subprocess.Popen(
                ["gdalinfo", "-json", "-proj4", path], 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace'
            )
            out, _ = process.communicate()
            data = json.loads(out)
            
            if "coordinateSystem" in data:
                cs = data["coordinateSystem"]
                wkt = cs.get("wkt", "")
                proj4 = cs.get("proj4", "")
                
                if "46.8916666667" in wkt or "46.891667" in wkt or "46.8916666667" in proj4:
                    return "MSK-05 (Dagestan)"
                if 'ID["EPSG",3857]' in wkt or "Pseudo-Mercator" in wkt:
                    return "EPSG:3857 (Google)"
                if 'ID["EPSG",4326]' in wkt:
                    return "EPSG:4326 (WGS84)"
                if wkt and 'PROJCRS' in wkt:
                    return "Custom / Unknown Projection"

            return "Unknown"
        except Exception as e:
            print(f"Error detecting CRS: {e}")
            return "Unknown"

    @staticmethod
    def get_bounds(path):
        """Получает границы (bounds)"""
        try:
            process = subprocess.Popen(
                ["gdalinfo", "-json", path], 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace'
            )
            out, _ = process.communicate()
            data = json.loads(out)
            coords = data.get("cornerCoordinates", {})
            
            def get_coord(key, idx):
                val = coords.get(key)
                if val and len(val) > idx: return val[idx]
                return 0.0

            all_x = [get_coord("upperLeft", 0), get_coord("lowerRight", 0), 
                     get_coord("upperRight", 0), get_coord("lowerLeft", 0)]
            all_y = [get_coord("upperLeft", 1), get_coord("lowerRight", 1), 
                     get_coord("upperRight", 1), get_coord("lowerLeft", 1)]
            
            return {
                "north": max(all_y), "south": min(all_y), 
                "east": max(all_x), "west": min(all_x)
            }
        except:
            return {"north": 0, "south": 0, "east": 0, "west": 0}

    def check_is_cog(self, file_path):
        """
        Проверяет, является ли файл Cloud Optimized GeoTIFF.
        Использует binding gdal для проверки метаданных структуры.
        """
        try:
            ds = gdal.Open(file_path)
            if not ds:
                return False
            
            # Получаем метаданные структуры изображения
            metadata = ds.GetMetadata("IMAGE_STRUCTURE")
            layout = metadata.get("LAYOUT", "")
            
            # Если указано COG, значит файл оптимизирован
            if layout == "COG":
                return True
                
            return False
        except Exception as e:
            print(f"Error checking COG: {e}")
            return False

    def get_footprint_wkt(self, file_path):
        """
        Создает WKT (Well-Known Text) полигон границ изображения,
        перепроецированный в EPSG:4326 для записи в БД.
        """
        try:
            ds = gdal.Open(file_path)
            if not ds:
                return None

            # 1. Получаем гео-трансформацию (координаты пикселей -> координаты карты)
            gt = ds.GetGeoTransform()
            width = ds.RasterXSize
            height = ds.RasterYSize

            # Точный расчет углов:
            min_x = gt[0]
            max_y = gt[3]
            max_x = gt[0] + width * gt[1]
            min_y = gt[3] + height * gt[5]

            # Создаем кольцо (LinearRing)
            ring = ogr.Geometry(ogr.wkbLinearRing)
            ring.AddPoint(min_x, max_y) # TL
            ring.AddPoint(max_x, max_y) # TR
            ring.AddPoint(max_x, min_y) # BR
            ring.AddPoint(min_x, min_y) # BL
            ring.AddPoint(min_x, max_y) # Close ring

            # Создаем полигон
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)

            # 2. Определяем исходную и целевую проекции
            src_wkt = ds.GetProjection()
            if not src_wkt:
                # Если проекции нет, вернуть None или попытаться использовать raw
                return None

            src_srs = osr.SpatialReference()
            src_srs.ImportFromWkt(src_wkt)

            tgt_srs = osr.SpatialReference()
            tgt_srs.ImportFromEPSG(4326) # WGS 84
            # Важно: Force traditional axis order (Long, Lat) для WKT
            tgt_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

            # 3. Трансформируем геометрию
            transform = osr.CoordinateTransformation(src_srs, tgt_srs)
            poly.Transform(transform)

            # [FIX] Принудительно убираем Z-координату (делаем 2D), 
            # чтобы PostGIS не ругался "Geometry has Z dimension"
            poly.FlattenTo2D()

            # Возвращаем строку WKT
            return poly.ExportToWkt()

        except Exception as e:
            print(f"Error creating footprint WKT: {e}")
            return None

    def run_background_process(self, cmd, input_path, output_path, task_id, task_service, success_callback, start_percent=10):
        """
        Запускает процесс и обновляет статус через task_service.
        Блокирует текущий поток (должна запускаться внутри Thread).
        """
        try:
            current_state = {
                "status": "processing",
                "progress": start_percent,
                "message": "Processing started..."
            }
            task_service.save_state(task_id, current_state)

            input_size = os.path.getsize(input_path) if os.path.exists(input_path) else 1
            print(f"Task {task_id}: Executing GDAL command...")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            start_time = time.time()
            last_update_time = 0

            while process.poll() is None:
                if time.time() - last_update_time > 0.5:
                    # 1. Прогресс по файлу
                    file_progress = start_percent
                    if os.path.exists(output_path):
                        current_size = os.path.getsize(output_path)
                        if input_size > 0:
                            ratio = current_size / input_size
                            if ratio > 1.2: ratio = 1.0 
                            remaining_range = 95 - start_percent
                            file_progress = start_percent + int(ratio * remaining_range)
                    
                    # 2. Эмуляция прогресса
                    elapsed = time.time() - start_time
                    time_factor = elapsed / 10.0
                    asymptotic_part = (1 - (1 / (1 + time_factor * 0.5))) 
                    time_progress = start_percent + int((99 - start_percent) * asymptotic_part)

                    final_progress = max(file_progress, time_progress)
                    if final_progress >= 100: final_progress = 99

                    current_state["progress"] = final_progress
                    task_service.save_state(task_id, current_state)
                    last_update_time = time.time()
                
                time.sleep(0.5)

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                err_msg = stderr.decode('utf-8', errors='replace')
                raise Exception(f"GDAL Error: {err_msg}")

            print(f"Task {task_id}: GDAL finished.")
            
            # Финализация (вызов колбэка для БД/S3)
            # Колбэк должен вернуть dict с результатами, который мы сохраним
            result = success_callback()
            
            current_state.update({
                "progress": 100,
                "status": "success",
                "result": result,
                "message": "Completed"
            })
            task_service.save_state(task_id, current_state)

        except Exception as e:
            traceback.print_exc()
            current_state.update({
                "status": "error",
                "progress": 0,
                "error": str(e),
                "message": "Failed"
            })
            task_service.save_state(task_id, current_state)
        finally:
            # Очистка
            if os.path.exists(input_path): 
                try: os.remove(input_path)
                except: pass
            if os.path.exists(output_path): 
                try: os.remove(output_path)
                except: pass