"""Run inside the tools image, with no network and as its unprivileged user."""
from pathlib import Path
from tempfile import TemporaryDirectory
from osgeo import gdal, osr
from server.geo.raster import inspect_raster


with TemporaryDirectory() as directory:
    source = Path(directory) / "smoke.tif"
    dataset = gdal.GetDriverByName("GTiff").Create(str(source), 100, 100, 1, gdal.GDT_Byte)
    dataset.SetGeoTransform((47, .001, .001, 43, .001, -.001))
    reference = osr.SpatialReference()
    reference.ImportFromEPSG(4326)
    dataset.SetProjection(reference.ExportToWkt())
    dataset = None
    report = inspect_raster(source)
    assert abs(report["wgs84_bounds"]["north"] - 43.1) < 1e-8
    assert report["publication_ready"] is False
    print("Offline tools image: native GDAL inspection passed")
