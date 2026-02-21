# server/services/gdal_service.py
import os
import traceback
from osgeo import gdal, osr, ogr

# Включаем использование исключений для GDAL, чтобы ошибки нормально ловились в try/except
gdal.UseExceptions()

class GdalService:
    
    @staticmethod
    def get_crs(path):
        """Определяет проекцию (МСК-05, Google, WGS84) с помощью нативного GDAL"""
        try:
            ds = gdal.Open(path)
            if not ds:
                return "Unknown"
                
            wkt = ds.GetProjection()
            if not wkt:
                return "Unknown"

            srs = osr.SpatialReference()
            srs.ImportFromWkt(wkt)
            
            wkt_str = srs.ExportToWkt()
            proj4_str = srs.ExportToProj4()
            
            if "46.8916666667" in wkt_str or "46.891667" in wkt_str or "46.8916666667" in proj4_str:
                return "MSK-05 (Dagestan)"
            if 'ID["EPSG",3857]' in wkt_str or "Pseudo-Mercator" in wkt_str:
                return "EPSG:3857 (Google)"
            if 'ID["EPSG",4326]' in wkt_str:
                return "EPSG:4326 (WGS84)"
                
            # Если проекция неизвестна нашей логике, пытаемся вытащить её название
            if srs.IsProjected():
                name = srs.GetAttrValue('PROJCS')
                return name if name else "Custom / Unknown Projection"
            elif srs.IsGeographic():
                name = srs.GetAttrValue('GEOGCS')
                return name if name else "Custom / Unknown Projection"

            return "Custom / Unknown Projection"
        except Exception as e:
            print(f"Error detecting CRS: {e}")
            return "Unknown"
        finally:
            ds = None # Освобождаем память

    @staticmethod
    def get_bounds(path):
        """Получает границы (bounds) напрямую из GeoTransform"""
        try:
            ds = gdal.Open(path)
            if not ds:
                return {"north": 0, "south": 0, "east": 0, "west": 0}

            gt = ds.GetGeoTransform()
            width = ds.RasterXSize
            height = ds.RasterYSize

            # Вычисляем крайние точки
            min_x = gt[0]
            max_y = gt[3]
            max_x = gt[0] + width * gt[1] + height * gt[2]
            min_y = gt[3] + width * gt[4] + height * gt[5]

            return {
                "north": max_y if max_y > min_y else min_y,
                "south": min_y if min_y < max_y else max_y,
                "east": max_x if max_x > min_x else min_x,
                "west": min_x if min_x < max_x else max_x
            }
        except Exception as e:
            print(f"Error getting bounds: {e}")
            return {"north": 0, "south": 0, "east": 0, "west": 0}
        finally:
            ds = None

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
        finally:
            ds = None

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

            # Принудительно убираем Z-координату (делаем 2D), 
            # чтобы PostGIS не ругался "Geometry has Z dimension"
            poly.FlattenTo2D()

            # Возвращаем строку WKT
            return poly.ExportToWkt()

        except Exception as e:
            print(f"Error creating footprint WKT: {e}")
            return None
        finally:
            ds = None