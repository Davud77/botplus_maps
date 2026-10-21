import unittest
from server.services.upload_names import ortho_upload_key


class UploadNameTests(unittest.TestCase):
    def test_client_paths_never_control_destination(self):
        for name in ["../../image.tif", "/etc/image.tif", "C:\\temp\\image.tif"]:
            key = ortho_upload_key(name)
            self.assertNotIn("/", key)
            self.assertNotIn("\\", key)
            self.assertTrue(key.endswith("_image.tif"))

    def test_same_names_have_different_keys(self):
        self.assertNotEqual(ortho_upload_key("same.tif"), ortho_upload_key("same.tif"))

    def test_russian_filenames_are_supported(self):
        self.assertTrue(ortho_upload_key("Ортофотоплан.tiff").endswith("_orthophoto.tiff"))

    def test_empty_and_non_tiff_names_fail(self):
        for name in [None, "", "test.jpg", "test.tif.exe"]:
            with self.assertRaises(ValueError):
                ortho_upload_key(name)
