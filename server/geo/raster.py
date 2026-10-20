"""Metadata-only inspection of local rasters. Never reads an entire pixel array."""
import math
from pathlib import Path

from .affine import point_bounds, raster_boundary


def _gdal_modules():
    try:
        from osgeo import gdal, ogr, osr
    except ImportError as exc:
        raise RuntimeError("GDAL Python bindings are unavailable. Use Dockerfile.tools or install matching GDAL bindings.") from exc
    gdal.UseExceptions()
    # Inspection must not fetch datum grids or other resources from the Internet.
    osr.SetPROJEnableNetwork(False)
    return gdal, ogr, osr


def spatial_reference(definition, osr):
    if not definition or not definition.strip():
        raise ValueError("Source CRS is missing. Supply --source-crs or --crs-file; CRS will not be guessed.")
    if definition.strip().lower().startswith(("http:", "https:", "/vsi", "ftp:")):
        raise ValueError("Remote CRS definitions are disabled; supply a local CRS definition")
    srs = osr.SpatialReference()
    if srs.SetFromUserInput(definition) != 0:
        raise ValueError("Cannot parse source CRS")
    if srs.Validate() != 0:
        raise ValueError("Source CRS is invalid")
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def footprint_wgs84(dataset, source_srs, ogr, osr):
    osr.SetPROJEnableNetwork(False)
    transform = dataset.GetGeoTransform(can_return_null=True)
    if transform is None:
        raise ValueError("Raster has no affine georeferencing; GCP/RPC-only rasters require a preparation step")
    ring = ogr.Geometry(ogr.wkbLinearRing)
    # Densification accounts for nonlinear reprojection along the raster edges.
    for x, y in raster_boundary(transform, dataset.RasterXSize, dataset.RasterYSize, segments=64):
        ring.AddPoint_2D(x, y)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    target = spatial_reference("EPSG:4326", osr)
    options = osr.CoordinateTransformationOptions()
    options.SetBallparkAllowed(False)
    operation = osr.CreateCoordinateTransformation(source_srs, target, options)
    if operation is None or polygon.Transform(operation) != 0:
        raise ValueError("Cannot transform source CRS to WGS84 with installed local datum grids")
    points = polygon.GetGeometryRef(0).GetPoints()
    if not all(math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90
               for x, y, *_ in points):
        raise ValueError("Transformation produced invalid longitude/latitude")
    if any(abs(a[0] - b[0]) > 180 for a, b in zip(points, points[1:])):
        raise ValueError("Antimeridian-crossing footprint requires splitting before publication")
    polygon.FlattenTo2D()
    return polygon.ExportToWkt(), point_bounds([(p[0], p[1]) for p in points])


def inspect_raster(source, source_crs=None):
    """Read headers, CRS and overview metadata from a local file, without conversion."""
    path = Path(source).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Source must be a local regular file")
    before = path.stat()
    gdal, ogr, osr = _gdal_modules()
    dataset = gdal.OpenEx(str(path), gdal.OF_RASTER | gdal.OF_READONLY, allowed_drivers=["GTiff"])
    if dataset is None:
        raise ValueError("Cannot open GeoTIFF raster")
    try:
        embedded = dataset.GetProjectionRef()
        srs = spatial_reference(source_crs or embedded, osr)
        transform = dataset.GetGeoTransform(can_return_null=True)
        if transform is None:
            raise ValueError("Raster has no affine georeferencing")
        native = point_bounds(raster_boundary(transform, dataset.RasterXSize, dataset.RasterYSize))
        footprint, wgs84 = footprint_wgs84(dataset, srs, ogr, osr)
        bands = []
        for index in range(1, dataset.RasterCount + 1):
            band = dataset.GetRasterBand(index)
            nodata = band.GetNoDataValue()
            bands.append({"band": index, "data_type": gdal.GetDataTypeName(band.DataType),
                          "block_size": list(band.GetBlockSize()),
                          "nodata": nodata if nodata is None or math.isfinite(nodata) else str(nodata),
                          "overviews": [list((band.GetOverview(i).XSize, band.GetOverview(i).YSize))
                                        for i in range(band.GetOverviewCount())]})
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed during inspection; retry after the producer closes the file")
        warnings = []
        if source_crs:
            warnings.append("CRS override applies to this report only; the source file has not been changed.")
        if max(dataset.RasterXSize, dataset.RasterYSize) > 512 and any(not b["overviews"] for b in bands):
            warnings.append("Large raster has bands without overviews; prepare a COG before publication.")
        return {"schema_version": 1, "source": str(path), "size_bytes": before.st_size,
                "mtime_ns": before.st_mtime_ns, "driver": dataset.GetDriver().ShortName,
                "width": dataset.RasterXSize, "height": dataset.RasterYSize,
                "crs_wkt": srs.ExportToWkt(["FORMAT=WKT2_2019"]),
                "crs_authority": srs.GetAuthorityName(None), "crs_code": srs.GetAuthorityCode(None),
                "crs_overridden": bool(source_crs), "native_bounds": native,
                "wgs84_bounds": wgs84, "footprint_wkt": footprint, "bands": bands,
                "cog_layout_hint": dataset.GetMetadata("IMAGE_STRUCTURE").get("LAYOUT") == "COG",
                "validation": "metadata_only", "publication_ready": False, "warnings": warnings}
    finally:
        dataset = None
