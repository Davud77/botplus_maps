"""Managed files on a local filesystem or an administrator-mounted NAS.

Keys are relative to one namespace. Source datasets live in separate read-only
roots and are never modified by this class. No directory scans are used to serve
catalogues: PostgreSQL holds the keys.
"""
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from flask import abort, send_file


class FileStorage:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve(strict=True)

    def path(self, key):
        if not isinstance(key, str) or not key or '\\' in key or '\x00' in key or ':' in key:
            raise ValueError('Invalid file key')
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {'', '.', '..'} for part in key.split('/')):
            raise ValueError('File key must be relative to its storage namespace')
        target = self.root
        for part in relative.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError('Symlinks are not permitted in managed storage')
        if not target.resolve().is_relative_to(self.root):
            raise ValueError('File is outside its storage namespace')
        return target

    def save_file(self, file_stream, filename, content_type=None):
        """Bounded-memory write; publish only complete, fsynced files, never replace."""
        target = self.path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Validate again after making directories, before publishing the file.
        target = self.path(filename)
        descriptor, temporary = tempfile.mkstemp(prefix='.upload-', dir=target.parent)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                shutil.copyfileobj(file_stream, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            # Hard-link publication is atomic and fails if the key already exists.
            # Both names are on the same filesystem, including NFS.
            os.link(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return filename

    def upload_file(self, filename, filepath, content_type=None):
        with open(filepath, 'rb') as stream:
            self.save_file(stream, filename, content_type)
        return True

    def get_local_file_path(self, filename):
        path = self.path(filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        return str(path)

    def send_local_file(self, filename, mimetype=None, *, as_attachment=False):
        try:
            path = self.get_local_file_path(filename)
        except (ValueError, FileNotFoundError):
            abort(404)
        # Werkzeug streams the file and supports conditional/range requests.
        return send_file(path, mimetype=mimetype, conditional=True,
                         as_attachment=as_attachment, download_name=Path(filename).name)

    def delete_file(self, filename):
        self.path(filename).unlink(missing_ok=True)
