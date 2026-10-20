import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from server.cli import main
from server.geo.raster import inspect_raster

try:
    from osgeo import gdal, osr
    gdal.UseExceptions()
except ImportError:
    if os.environ.get("REQUIRE_GDAL_TESTS") == "1":
        raise
    gdal = osr = None


@unittest.skipIf(gdal is None, "Native GDAL unavailable; the Linux CI raster job runs these tests")
class RasterInspectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ortho.tif"

    def raster(self, crs="EPSG:4326", transform=(47, 0.01, 0, 43, 0, -0.01)):
        dataset = gdal.GetDriverByName("GTiff").Create(str(self.path), 100, 100, 1, gdal.GDT_Byte)
        dataset.SetGeoTransform(transform)
        if crs:
            reference = osr.SpatialReference()
            reference.SetFromUserInput(crs)
            dataset.SetProjection(reference.ExportToWkt())
        dataset = None

    def test_wgs84_and_metadata_only_contract(self):
        self.raster()
        result = inspect_raster(self.path)
        self.assertAlmostEqual(result["wgs84_bounds"]["west"], 47)
        self.assertAlmostEqual(result["wgs84_bounds"]["north"], 43)
        self.assertFalse(result["publication_ready"])
        self.assertEqual(result["validation"], "metadata_only")
        self.assertEqual(result["bands"][0]["data_type"], "Byte")

    def test_legacy_service_uses_rotation_aware_bounds(self):
        from server.services.gdal_service import GdalService
        self.raster(transform=(47, .001, .001, 43, .001, -.001))
        bounds = GdalService.get_bounds(str(self.path))
        self.assertAlmostEqual(bounds["north"], 43.1)
        self.assertAlmostEqual(bounds["south"], 42.9)
        self.assertIn("POLYGON", GdalService().get_footprint_wkt(str(self.path)))

    def test_rotated_raster(self):
        self.raster(transform=(47, .001, .001, 43, .001, -.001))
        result = inspect_raster(self.path)
        self.assertAlmostEqual(result["native_bounds"]["north"], 43.1)
        self.assertAlmostEqual(result["native_bounds"]["south"], 42.9)

    def test_custom_crs_without_epsg_is_preserved(self):
        definition = "+proj=tmerc +lat_0=0 +lon_0=46.8916666667 +k=1 +x_0=1000000 +y_0=-5000000 +datum=WGS84 +units=m +no_defs"
        self.raster(crs=definition, transform=(1000000, 1, 0, 0, 0, -1))
        result = inspect_raster(self.path)
        self.assertIn("46.8916666667", result["crs_wkt"])
        self.assertAlmostEqual(result["wgs84_bounds"]["west"], 46.8916666667, places=5)

    def test_missing_crs_fails_without_guessing(self):
        self.raster(crs=None)
        with self.assertRaisesRegex(ValueError, "CRS is missing"):
            inspect_raster(self.path)

    def test_crs_override_does_not_modify_original(self):
        self.raster(crs=None)
        original = self.path.read_bytes()
        result = inspect_raster(self.path, source_crs="EPSG:4326")
        self.assertTrue(result["crs_overridden"])
        self.assertEqual(original, self.path.read_bytes())

    def test_cli_accepts_local_prj(self):
        self.raster(crs=None)
        definition = Path(self.directory.name) / "local.prj"
        definition.write_text("EPSG:4326", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["inspect-raster", str(self.path), "--crs-file", str(definition)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["schema_version"], 1)

    def test_antimeridian_requires_explicit_preparation(self):
        self.raster(transform=(179.5, .02, 0, 43, 0, -.01))
        with self.assertRaises(ValueError):
            inspect_raster(self.path)


class CliFailureTests(unittest.TestCase):
    def test_missing_file_has_nonzero_exit(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(main(["inspect-raster", "/path/which/does/not/exist.tif"]), 2)
        self.assertIn("Inspection failed", stderr.getvalue())
