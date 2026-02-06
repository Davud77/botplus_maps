# ./backend/managers/pano_manager.py

from models.pano import Pano
import psycopg2

class PanoManager:
    def __init__(self, db_conn):
        self.db = db_conn  # Соединение psycopg2

    def create_pano(self, pano):
        cursor = self.db.cursor()
        
        # 1. Запрос INSERT соответствует вашей таблице photos_4326
        # Примечание: поля user_id и tags закомментированы, так как их нет на вашем скриншоте базы.
        # Если вы добавите их (ALTER TABLE ...), раскомментируйте строки ниже.
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
                -- , user_id, tags
            )
            VALUES (
                %s, 
                %s,
                ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326), 
                %s, 
                %s, 
                0, 0, 
                %s, %s, 
                'uploaded',
                0
                -- , %s, %s
            )
            RETURNING id;
        """
        
        # 2. Подготовка данных
        # PostGIS ST_MakePoint принимает (X, Y, Z) -> (Longitude, Latitude, Altitude)
        altitude = pano.altitude if pano.altitude is not None else 0.0
        
        values = [
            pano.filename,       # filename
            pano.filename,       # path (используем имя файла или полный путь)
            pano.longitude,      # X для geom
            pano.latitude,       # Y для geom
            altitude,            # Z для geom
            pano.first_photo_date, # timestamp
            altitude,            # altitude (numeric)
            str(pano.longitude), # longitude (в базе это varchar)
            str(pano.latitude)   # latitude (в базе это varchar)
            # , pano.user_id     # Раскомментировать, если добавили колонку
            # , pano.tags        # Раскомментировать, если добавили колонку
        ]

        try:
            cursor.execute(query, tuple(values))
            new_id = cursor.fetchone()[0]
            self.db.commit()
            return new_id
        except Exception as e:
            self.db.rollback()
            raise e
        finally:
            cursor.close()

    def get_pano_list(self):
        """
        Возвращает список всех панорам с координатами для отображения на карте.
        Использует PostGIS функции для извлечения координат из геометрии.
        """
        cursor = self.db.cursor()
        query = """
            SELECT 
                id, 
                ST_Y(geom::geometry) as latitude, 
                ST_X(geom::geometry) as longitude 
            FROM public.photos_4326
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        
        # Преобразуем в список словарей для JSON-ответа
        return [{"id": r[0], "latitude": r[1], "longitude": r[2]} for r in rows]

    def get_pano_by_id(self, pano_id):
        """
        Получает полную информацию о панораме по ID.
        """
        cursor = self.db.cursor()
        query = """
            SELECT 
                id, 
                filename, 
                path, 
                "timestamp", 
                altitude,
                latitude, 
                longitude
            FROM public.photos_4326 
            WHERE id = %s
        """
        cursor.execute(query, (pano_id,))
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "id": row[0],
                "filename": row[1],
                "path": row[2],
                "first_photo_date": row[3],
                "altitude": float(row[4]) if row[4] is not None else 0,
                "latitude": float(row[5]) if row[5] else 0,
                "longitude": float(row[6]) if row[6] else 0
            }
        return None

    def update_pano(self, pano_id, updated_fields):
        """
        Обновляет поля панорамы. Если меняются координаты, перестраивает geom.
        """
        if not updated_fields:
            return None
        
        cursor = self.db.cursor()
        set_clauses = []
        values = []

        # Специальная обработка координат: нужно обновить и поля, и geom
        lat = updated_fields.get('latitude')
        lon = updated_fields.get('longitude')
        
        if lat is not None or lon is not None:
            # Получаем текущие значения, если меняется только одно из полей
            if lat is None or lon is None:
                current = self.get_pano_by_id(pano_id)
                if current:
                    lat = lat if lat is not None else current['latitude']
                    lon = lon if lon is not None else current['longitude']
                else:
                    # Если панорама не найдена, прерываем
                    cursor.close()
                    return 
            
            # Обновляем геометрию
            set_clauses.append("geom = ST_SetSRID(ST_MakePoint(%s, %s, 0), 4326)")
            values.extend([lon, lat])
            
            # Обновляем текстовые поля
            if 'latitude' in updated_fields:
                set_clauses.append("latitude = %s")
                values.append(str(lat))
            if 'longitude' in updated_fields:
                set_clauses.append("longitude = %s")
                values.append(str(lon))

        # Обработка остальных полей
        for field, value in updated_fields.items():
            if field not in ['latitude', 'longitude', 'geom']:
                # Маппинг полей модели на поля БД
                db_field = field
                if field == 'first_photo_date': db_field = 'timestamp'
                
                set_clauses.append(f'"{db_field}" = %s')
                values.append(value)

        if not set_clauses:
            cursor.close()
            return

        query = f"UPDATE public.photos_4326 SET {', '.join(set_clauses)} WHERE id = %s"
        values.append(pano_id)

        try:
            cursor.execute(query, tuple(values))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
        finally:
            cursor.close()

    def delete_pano(self, pano_id):
        cursor = self.db.cursor()
        query = "DELETE FROM public.photos_4326 WHERE id = %s"
        try:
            cursor.execute(query, (pano_id,))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
        finally:
            cursor.close()