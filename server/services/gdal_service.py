import subprocess
import json
import os
import time
import traceback

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