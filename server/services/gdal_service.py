# server/services/gdal_service.py
from osgeo import gdal, osr, ogr

try:  # Package imports in tests, flat imports in the legacy Flask entrypoint.
    from ..geo.affine import point_bounds, raster_boundary
    from ..geo.raster import footprint_wgs84, spatial_reference
except ImportError:
    from geo.affine import point_bounds, raster_boundary
    from geo.raster import footprint_wgs84, spatial_reference

# Включаем использование исключений для GDAL, чтобы ошибки нормально ловились в try/except
gdal.UseExceptions()

class GdalService:

    @staticmethod
    def get_crs(path):
        """Preserve custom CRS definitions rather than guessing from projection parameters."""
        ds = gdal.Open(path)
        if not ds or not ds.GetProjection():
            return "Unknown"
        try:
            srs = osr.SpatialReference()
            srs.ImportFromWkt(ds.GetProjection())
            authority, code = srs.GetAuthorityName(None), srs.GetAuthorityCode(None)
            return f"{authority}:{code}" if authority and code else srs.ExportToWkt(["FORMAT=WKT2_2019"])
        finally:
            ds = None

    @staticmethod
    def get_bounds(path):
        ds = gdal.Open(path)
        if not ds:
            raise ValueError("Cannot open raster")
        try:
            transform = ds.GetGeoTransform(can_return_null=True)
            if transform is None:
                raise ValueError("Raster has no affine georeferencing")
            return point_bounds(raster_boundary(transform, ds.RasterXSize, ds.RasterYSize))
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
        """Build a densified WGS84 footprint using the declared source CRS."""
        ds = gdal.Open(file_path)
        if not ds:
            raise ValueError("Cannot open raster")
        try:
            srs = spatial_reference(ds.GetProjection(), osr)
            footprint, _ = footprint_wgs84(ds, srs, ogr, osr)
            return footprint
        finally:
            ds = None
