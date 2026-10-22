import tempfile
from pathlib import Path
import unittest
from PIL import Image
from server.services.media_metadata import media_kind, read_media_metadata, display_name

class MediaMetadataTests(unittest.TestCase):
    def test_regular_gopro_photo_is_never_stretched_to_sphere(self):
        self.assertEqual(media_kind(2704, 2028), 'photo')
        self.assertEqual(media_kind(2704, 2028, b'GPano:ProjectionType="equirectangular"'), 'photo')
    def test_full_gpano_and_legacy_equirectangular_export(self):
        self.assertEqual(media_kind(5760, 2880, b'GPano:ProjectionType="equirectangular"'), 'panorama')
        self.assertEqual(media_kind(5760, 2880), 'panorama')
        self.assertEqual(media_kind(32, 16), 'photo')
    def test_headers_and_display_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'photo.jpg'
            Image.new('RGB',(40,30)).save(path)
            self.assertEqual(read_media_metadata(path),{'width':40,'height':30,'media_type':'photo'})
        self.assertEqual(display_name('ab/cd/'+'a'*32+'_GP123.JPG'),'GP123.JPG')
        self.assertEqual(display_name('legacy.jpg'),'legacy.jpg')
