# server/controllers/pano_controller.py

from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import io
import os
import piexif
from PIL import Image
from datetime import datetime
import traceback
import logging

# Use centralized Database class
from database import Database
from storage import MinioStorage
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pano_blueprint = Blueprint("pano", __name__)

class PanoController:
    def __init__(self):
        # Use centralized Database class (connects via pgbouncer)
        self.db = Database()
        self.storage = MinioStorage()
        
        # Гарантируем, что таблица photos_4326 существует!
        self._ensure_table()
        
        # Ensure bucket exists
        if self.storage.client:
            try:
                if not self.storage.client.bucket_exists("panoramas"):
                    self.storage.client.make_bucket("panoramas")
            except Exception as e:
                logger.warning(f"MinIO bucket warning: {e}")

    def _ensure_table(self):
        """Создает таблицу photos_4326 точно как на скриншоте, если ее нет"""
        try:
            cursor = self.db.get_cursor()
            query = """
                CREATE TABLE IF NOT EXISTS public.photos_4326 (
                    id SERIAL PRIMARY KEY,
                    geom geometry(PointZ, 4326),
                    path VARCHAR,
                    filename VARCHAR,
                    directory VARCHAR,
                    altitude NUMERIC,
                    direction NUMERIC,
                    rotation INTEGER,
                    longitude VARCHAR,
                    latitude VARCHAR,
                    "timestamp" TIMESTAMP,
                    "order" INTEGER
                );
            """
            cursor.execute(query)
            self.db.commit()
            logger.info("Table photos_4326 is ready.")
        except Exception as e:
            logger.warning(f"Could not initialize photos_4326: {e}")
            if self.db.connection:
                self.db.connection.rollback()

    @staticmethod
    def register_routes(blueprint):
        controller = PanoController()
        
        # List (with BBOX support)
        blueprint.add_url_rule("/panoramas", view_func=controller.get_panoramas, methods=["GET"])
        
        # Upload
        blueprint.add_url_rule("/upload", view_func=controller.upload_pano_files, methods=["POST", "OPTIONS"])
        
        # Info
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.get_pano_info, methods=["GET"])
        
        # Download / Image
        blueprint.add_url_rule("/pano_info/<int:pano_id>/download", view_func=controller.download_pano_file, methods=["GET"])
        blueprint.add_url_rule("/panoramas/<path:filename>", view_func=controller.get_pano_image_direct, methods=["GET"])
        
        # Delete / Update
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.delete_pano, methods=["DELETE"])
        blueprint.add_url_rule("/pano_info/<int:pano_id>", view_func=controller.update_pano, methods=["PUT"])

    @cross_origin()
    def get_panoramas(self):
        """
        Returns list of panoramas. Supports BBOX filtering.
        """
        try:
            # 1. Filter params
            north = request.args.get('north', type=float)
            south = request.args.get('south', type=float)
            east = request.args.get('east', type=float)
            west = request.args.get('west', type=float)
            limit = request.args.get('limit', type=int, default=5000)

            cursor = self.db.get_cursor()

            # 2. Build Query
            if north is not None and south is not None:
                # PostGIS BBOX search
                query = """
                    SELECT 
                        id, 
                        NULLIF(latitude, '')::float AS latitude, 
                        NULLIF(longitude, '')::float AS longitude, 
                        filename, 
                        directory,
                        "timestamp"
                    FROM public.photos_4326
                    WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                    ORDER BY id DESC
                    LIMIT %s
                """
                params = (west, south, east, north, limit)
            else:
                # Default: latest N
                query = """
                    SELECT 
                        id, 
                        NULLIF(latitude, '')::float AS latitude, 
                        NULLIF(longitude, '')::float AS longitude, 
                        filename, 
                        directory,
                        "timestamp"
                    FROM public.photos_4326
                    ORDER BY id DESC
                    LIMIT %s
                """
                params = (limit,)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 3. Format JSON
            results = []
            for row in rows:
                # Handle RealDictCursor or Tuple
                if isinstance(row, dict):
                    res = row
                else:
                    res = {
                        "id": row[0],
                        "latitude": row[1],
                        "longitude": row[2],
                        "filename": row[3],
                        "directory": row[4],
                        "timestamp": row[5]
                    }
                
                ts = res.get("timestamp")
                results.append({
                    "id": res["id"],
                    "latitude": res["latitude"] if res["latitude"] is not None else 0,
                    "longitude": res["longitude"] if res["longitude"] is not None else 0,
                    "filename": res["filename"],
                    "directory": res["directory"],
                    "timestamp": ts.isoformat() if ts else None
                })

            return jsonify(results)

        except Exception as e:
            logger.error(f"Error getting panoramas: {e}")
            traceback.print_exc()
            # If DB error, rollback to reset transaction state
            if self.db.connection:
                self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_info(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            query = """
                SELECT id, latitude, longitude, altitude, direction, filename, directory, "timestamp"
                FROM public.photos_4326 
                WHERE id = %s
            """
            cursor.execute(query, (pano_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict): data = row
                else: 
                    data = {
                        "id": row[0], "latitude": row[1], "longitude": row[2], 
                        "altitude": row[3], "direction": row[4], 
                        "filename": row[5], "directory": row[6], "timestamp": row[7]
                    }
                
                result = {
                    "id": data["id"],
                    "latitude": float(data["latitude"]) if data["latitude"] else 0,
                    "longitude": float(data["longitude"]) if data["longitude"] else 0,
                    "altitude": float(data["altitude"]) if data["altitude"] else 0,
                    "direction": float(data["direction"]) if data["direction"] else 0,
                    "filename": data["filename"],
                    "directory": data["directory"],
                    "timestamp": data["timestamp"].isoformat() if data["timestamp"] else None
                }
                return jsonify(result)
            else:
                return jsonify({"error": "Not found"}), 404
        except Exception as e:
            if self.db.connection: self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def download_pano_file(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cursor.fetchone()
            
            if not res:
                return jsonify({"error": "Not found"}), 404

            filename = res['filename'] if isinstance(res, dict) else res[0]
            
            # Switch bucket context
            orig_bucket = self.storage.bucket_name
            self.storage.bucket_name = "panoramas"
            
            # Try MinIO
            response = None
            if self.storage.client:
                try:
                    response = self.storage.send_local_file(filename, mimetype="image/jpeg")
                except: pass
            
            self.storage.bucket_name = orig_bucket
            
            if response: return response
            return jsonify({"error": "File not found in storage"}), 404

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def get_pano_image_direct(self, filename):
        try:
            orig_bucket = self.storage.bucket_name
            self.storage.bucket_name = "panoramas"
            response = self.storage.send_local_file(filename, mimetype="image/jpeg")
            self.storage.bucket_name = orig_bucket
            return response
        except Exception as e:
            return jsonify({"error": str(e)}), 404

    @cross_origin()
    def upload_pano_files(self):
        if request.method == "OPTIONS":
            return "", 200

        uploaded_files = request.files.getlist("files")
        successful = []
        failed = []

        orig_bucket = self.storage.bucket_name
        self.storage.bucket_name = "panoramas"

        try:
            for file in uploaded_files:
                try:
                    original_name = file.filename
                    file_content = file.read()
                    
                    # 1. Parse EXIF
                    img_stream = io.BytesIO(file_content)
                    lat, lon, alt, direction, dt = self._parse_exif_data(img_stream)
                    
                    if lat is None or lon is None:
                        raise ValueError("No GPS data found")

                    # 2. Filename
                    timestamp_str = dt.strftime("%Y%m%d_%H%M%S") if dt else "nodate"
                    new_filename = f"pano_{timestamp_str}_{original_name}"
                    file_path = f"panoramas/{new_filename}"

                    # 3. MinIO Upload
                    save_stream = io.BytesIO(file_content)
                    self.storage.save_file(save_stream, new_filename, content_type="image/jpeg")

                    # 4. DB Insert
                    self._insert_pano_db(new_filename, file_path, lat, lon, alt, direction, dt)
                    
                    successful.append(original_name)
                    logger.info(f"Uploaded {original_name}")

                except Exception as e:
                    logger.error(f"Error uploading {file.filename}: {e}")
                    failed.append(file.filename)

            return jsonify({
                "message": "Upload complete",
                "successful_uploads": successful,
                "failed_uploads": failed
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            self.storage.bucket_name = orig_bucket

    @cross_origin()
    def delete_pano(self, pano_id):
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT filename FROM public.photos_4326 WHERE id = %s", (pano_id,))
            res = cursor.fetchone()
            
            if res:
                filename = res['filename'] if isinstance(res, dict) else res[0]
                
                cursor.execute("DELETE FROM public.photos_4326 WHERE id = %s", (pano_id,))
                self.db.commit()
                
                orig = self.storage.bucket_name
                self.storage.bucket_name = "panoramas"
                self.storage.delete_file(filename)
                self.storage.bucket_name = orig
                
                return jsonify({"status": "deleted"})
            
            return jsonify({"error": "Not found"}), 404
        except Exception as e:
            if self.db.connection: self.db.connection.rollback()
            return jsonify({"error": str(e)}), 500

    @cross_origin()
    def update_pano(self, pano_id):
        return jsonify({"status": "error", "message": "Update not implemented"}), 501

    # --- HELPERS ---

    def _insert_pano_db(self, filename, path, lat, lon, alt, direction, timestamp):
        cursor = self.db.get_cursor()
        query = """
            INSERT INTO public.photos_4326 (
                geom, path, filename, directory, 
                altitude, direction, rotation, 
                longitude, latitude, "timestamp", "order"
            ) VALUES (
                ST_SetSRID(ST_MakePoint(%s, %s, %s), 4326),
                %s, %s, 'panoramas', 
                %s, %s, 0, 
                %s, %s, %s, 0
            )
        """
        values = (
            float(lon), float(lat), float(alt or 0),
            path, filename,
            float(alt or 0), float(direction or 0),
            str(lon), str(lat), timestamp or datetime.now()
        )
        cursor.execute(query, values)
        self.db.commit()

    def _parse_exif_data(self, stream):
        try:
            img = Image.open(stream)
            if "exif" not in img.info: return None, None, 0, 0, None
            exif_dict = piexif.load(img.info["exif"])
            
            lat, lon, alt = self._get_gps_coordinates(exif_dict)
            direction = self._get_direction(exif_dict)
            
            dt = None
            date_str = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
            if date_str:
                try:
                    if isinstance(date_str, bytes): date_str = date_str.decode()
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except: pass
            
            return lat, lon, alt, direction, dt
        except:
            return None, None, 0, 0, None

    def _get_gps_coordinates(self, exif_dict):
        gps = exif_dict.get("GPS", {})
        lat = lon = alt = None

        if piexif.GPSIFD.GPSLatitude in gps:
            lat = self._convert_to_degrees(gps[piexif.GPSIFD.GPSLatitude])
            if gps.get(piexif.GPSIFD.GPSLatitudeRef) == b'S': lat = -lat
        
        if piexif.GPSIFD.GPSLongitude in gps:
            lon = self._convert_to_degrees(gps[piexif.GPSIFD.GPSLongitude])
            if gps.get(piexif.GPSIFD.GPSLongitudeRef) == b'W': lon = -lon
            
        if piexif.GPSIFD.GPSAltitude in gps:
            alt = self._safe_rational(gps[piexif.GPSIFD.GPSAltitude])

        return lat, lon, alt

    def _get_direction(self, exif_dict):
        gps = exif_dict.get("GPS", {})
        val = gps.get(piexif.GPSIFD.GPSImgDirection)
        return self._safe_rational(val)

    def _convert_to_degrees(self, value):
        d = self._safe_rational(value[0])
        m = self._safe_rational(value[1])
        s = self._safe_rational(value[2])
        return d + (m / 60.0) + (s / 3600.0)

    def _safe_rational(self, value):
        if not value: return 0.0
        try:
            if isinstance(value, tuple) and len(value) == 2:
                return value[0] / value[1] if value[1] != 0 else 0.0
            return float(value)
        except: return 0.0

PanoController.register_routes(pano_blueprint)