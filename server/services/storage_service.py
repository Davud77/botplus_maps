"""Raster files shared by the API, processing worker and TiTiler."""
import shutil
from pathlib import Path
from storage import FileStorage
import config


class StorageService:
    def __init__(self):
        self.files = FileStorage(Path(config.MEDIA_ROOT) / 'orthophotos')

    def upload_file(self, filename, filepath, content_type='image/tiff'):
        return self.files.upload_file(filename, filepath, content_type)

    def download_file(self, filename, local_path):
        # Legacy processing copies only when a writable working file is needed.
        source = self.files.get_local_file_path(filename)
        shutil.copyfile(source, local_path)
        return True

    def get_local_file_path(self, filename):
        return self.files.get_local_file_path(filename)

    def delete_file(self, filename):
        self.files.delete_file(filename)

    def send_file(self, filename, mimetype='image/tiff'):
        return self.files.send_local_file(filename, mimetype=mimetype)
