# ./backend/managers/pano_manager.py

from models.pano import Pano
import json

class PanoManager:
    def __init__(self, db):
        self.db = db

    def create_pano(self, pano):
        """
        Создает запись о панораме в таблице photos_4326.
        Использует PostGIS для создания геометрии.
        """
        try:
            cursor = self.db.get_cursor()
            
            # SQL запрос для вставки
            query = """
                INSERT INTO public.photos_4326 (
                    filename, 
                    path,
                    geom, 
                    "timestamp", 
                    altitude, 
                    direction, 
                    rotation,
                    longitude,
                    latitude,
                    directory,
                    "order"
                )
                VALUES (
                    %s, 
                    %s,
                    ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326), 
                    %s, 
                    %s, 
                    %s, 
                    %s, 
                    %s, 
                    %s, 
                    'uploaded',
                    0
                )
                RETURNING id;
            """
            
            # Подготовка данных
            # 1. Координаты и высота
            lon = float(pano.longitude) if pano.longitude is not None else 0.0
            lat = float(pano.latitude) if pano.latitude is not None else 0.0
            alt = float(pano.altitude) if hasattr(pano, 'altitude') and pano.altitude else 0.0
            
            # 2. Ориентация (если есть в объекте Pano)
            heading = float(pano.heading) if hasattr(pano, 'heading') and pano.heading else 0.0
            roll = float(pano.roll) if hasattr(pano, 'roll') and pano.roll else 0.0
            
            # 3. Дата
            ts = pano.upload_date if hasattr(pano, 'upload_date') else None

            values = (
                pano.filename,       # filename
                pano.filename,       # path (используем имя файла как путь)
                lon,                 # X (geom)
                lat,                 # Y (geom)
                alt,                 # Z (geom)
                ts,                  # timestamp
                alt,                 # altitude
                heading,             # direction
                roll,                # rotation
                str(lon),            # longitude (varchar)
                str(lat)             # latitude (varchar)
            )

            cursor.execute(query, values)
            
            # Получаем ID новой записи
            row = cursor.fetchone()
            if isinstance(row, dict):
                new_id = row['id']
            else:
                new_id = row[0]
                
            self.db.commit()
            return new_id

        except Exception as e:
            print(f"Error creating pano: {e}")
            if self.db.connection:
                self.db.connection.rollback()
            raise e

    def get_all_panos(self):
        """
        Возвращает список всех панорам.
        """
        try:
            cursor = self.db.get_cursor()
            # Выбираем основные поля + координаты из геометрии (на всякий случай)
            query = """
                SELECT 
                    id, 
                    filename,
                    "timestamp" as upload_date,
                    altitude,
                    direction as heading,
                    rotation as roll,
                    latitude, 
                    longitude
                FROM public.photos_4326
                ORDER BY id DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            panos = []
            for row in rows:
                # Адаптация под RealDictCursor
                if isinstance(row, dict):
                    data = row
                else:
                    # Fallback
                    data = {
                        "id": row[0], "filename": row[1], "upload_date": row[2],
                        "altitude": row[3], "heading": row[4], "roll": row[5],
                        "latitude": row[6], "longitude": row[7]
                    }

                # Создаем объект Pano (или словарь, если Pano модель простая)
                # Здесь возвращаем словарь для совместимости с контроллером
                pano_dict = {
                    "id": data.get("id"),
                    "filename": data.get("filename"),
                    "latitude": float(data.get("latitude")) if data.get("latitude") else 0,
                    "longitude": float(data.get("longitude")) if data.get("longitude") else 0,
                    "heading": data.get("heading"),
                    "roll": data.get("roll"),
                    "altitude": data.get("altitude"),
                    "upload_date": str(data.get("upload_date"))
                }
                panos.append(pano_dict)
                
            return panos # Контроллер ждет список объектов/словарей, у которых есть метод to_dict или это уже словари
            
        except Exception as e:
            if self.db.connection:
                self.db.connection.rollback()
            raise e

    def get_pano_by_id(self, pano_id):
        """
        Получает одну панораму по ID.
        """
        try:
            cursor = self.db.get_cursor()
            query = """
                SELECT 
                    id, 
                    filename, 
                    path, 
                    "timestamp" as upload_date, 
                    altitude,
                    direction as heading,
                    rotation as roll,
                    latitude, 
                    longitude
                FROM public.photos_4326 
                WHERE id = %s
            """
            cursor.execute(query, (pano_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    data = row
                else:
                    data = {
                        "id": row[0], "filename": row[1], "path": row[2], 
                        "upload_date": row[3], "altitude": row[4], "heading": row[5],
                        "roll": row[6], "latitude": row[7], "longitude": row[8]
                    }
                
                # Возвращаем объект Pano
                return Pano(
                    pano_id=data.get("id"),
                    filename=data.get("filename"),
                    latitude=float(data.get("latitude")) if data.get("latitude") else 0,
                    longitude=float(data.get("longitude")) if data.get("longitude") else 0,
                    heading=data.get("heading"),
                    roll=data.get("roll"),
                    altitude=data.get("altitude"),
                    upload_date=data.get("upload_date")
                )
            return None
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def update_pano(self, pano_id, updated_fields):
        """
        Обновляет поля панорамы. Синхронизирует geom при изменении координат.
        """
        if not updated_fields:
            return

        try:
            cursor = self.db.get_cursor()
            set_clauses = []
            values = []

            # 1. Проверяем координаты
            lat = updated_fields.get('latitude')
            lon = updated_fields.get('longitude')
            
            # Если меняем координаты, нужно обновить geom
            if lat is not None or lon is not None:
                # Если передан только один параметр, нужно достать второй из базы
                if lat is None or lon is None:
                    current = self.get_pano_by_id(pano_id)
                    if current:
                        lat = lat if lat is not None else current.latitude
                        lon = lon if lon is not None else current.longitude
                    else:
                        return # Панорама не найдена
                
                set_clauses.append("geom = ST_SetSRID(ST_MakePoint(%s, %s, COALESCE(altitude, 0)), 4326)")
                values.extend([float(lon), float(lat)])
                
                # Обновляем текстовые поля координат
                if 'latitude' in updated_fields:
                    set_clauses.append("latitude = %s")
                    values.append(str(lat))
                if 'longitude' in updated_fields:
                    set_clauses.append("longitude = %s")
                    values.append(str(lon))

            # 2. Остальные поля
            field_map = {
                'heading': 'direction',
                'pitch': None, # Нет в таблице
                'roll': 'rotation',
                'upload_date': 'timestamp',
                'tags': None # Нет в таблице, если не добавили
            }

            for field, value in updated_fields.items():
                if field in ['latitude', 'longitude']: continue
                
                db_col = field_map.get(field, field)
                if db_col:
                    set_clauses.append(f'"{db_col}" = %s')
                    values.append(value)

            if not set_clauses:
                return

            query = f"UPDATE public.photos_4326 SET {', '.join(set_clauses)} WHERE id = %s"
            values.append(pano_id)

            cursor.execute(query, tuple(values))
            self.db.commit()
            
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise

    def delete_pano(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            query = "DELETE FROM public.photos_4326 WHERE id = %s"
            cursor.execute(query, (pano_id,))
            self.db.commit()
        except Exception:
            if self.db.connection:
                self.db.connection.rollback()
            raise