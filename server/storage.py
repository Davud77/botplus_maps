# server/storage.py

import os
import io
from typing import Optional, List
from flask import send_file, jsonify
from werkzeug.utils import secure_filename
from mimetypes import guess_type
import tempfile
import shutil


class LocalStorage:
    """
    Простое файловое хранилище на локальном диске.

    Базовая директория передаётся при инициализации (обычно config.MEDIA_ROOT).
    Все операции выполняются ТОЛЬКО внутри этой директории (есть защита от
    path traversal).

    Пример:
        from server import config
        storage = LocalStorage(config.MEDIA_ROOT)
        storage.save_file(file.stream, file.filename, subdir="panos")
    """

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    # -------------------- helpers --------------------

    def _safe_join(self, *parts: str) -> str:
        """
        Склеивает путь под base_dir и предотвращает выход за пределы хранилища.
        Создаёт отсутствующие промежуточные директории.
        """
        cleaned = [p.strip().lstrip("/\\") for p in parts if p]
        path = os.path.abspath(os.path.join(self.base_dir, *cleaned))
        if not path.startswith(self.base_dir):
            raise ValueError("Path traversal outside storage base")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    # --------------------- API -----------------------

    def save_file(
        self,
        file_stream: io.BufferedIOBase,
        filename: str,
        subdir: Optional[str] = None,
    ) -> str:
        """
        Сохраняет поток в base_dir[/subdir]/secure_filename.
        Возвращает абсолютный путь сохранённого файла.
        Пишем атомарно: во временный файл с последующим rename.
        """
        safe_name = secure_filename(filename) or "unnamed"
        rel_parts = (subdir, safe_name) if subdir else (safe_name,)
        dst = self._safe_join(*rel_parts)

        # Пишем во временный файл рядом с целевым
        dst_dir = os.path.dirname(dst)
        os.makedirs(dst_dir, exist_ok=True)

        # Попробуем перемотать поток
        try:
            file_stream.seek(0)
        except Exception:
            pass

        fd, tmp_path = tempfile.mkstemp(prefix=".upload-", dir=dst_dir)
        try:
            with os.fdopen(fd, "wb") as tmp:
                shutil.copyfileobj(file_stream, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
            # Атомарно заменяем
            os.replace(tmp_path, dst)
        finally:
            # На случай исключений
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        return dst

    def send_local_file(
        self,
        relative_path: str,
        *,
        mimetype: Optional[str] = None,
        as_attachment: bool = False,
        download_name: Optional[str] = None,
        conditional: bool = True,
    ):
        """
        Отдать локальный файл, расположенный внутри base_dir, безопасно.

        :param relative_path: относительный путь внутри хранилища
        :param mimetype: MIME-тип; если не указан — определяется по расширению
        :param as_attachment: отдать как скачиваемый файл
        :param download_name: имя файла для скачивания/отдачи
        :param conditional: включить поддержку 304/If-Modified-Since
        """
        abs_path = self._safe_join(relative_path)
        if not (os.path.exists(abs_path) and os.path.isfile(abs_path)):
            return jsonify({"error": "File not found"}), 404

        if not mimetype:
            guessed, _ = guess_type(abs_path)
            mimetype = guessed or "application/octet-stream"

        if download_name is None:
            download_name = os.path.basename(abs_path)

        return send_file(
            abs_path,
            mimetype=mimetype,
            as_attachment=as_attachment,
            download_name=download_name,
            conditional=conditional,
        )

    def send(self, relative_path: str, mimetype: str = "application/octet-stream"):
        """
        Backward-compat helper: историческое имя метода.
        Делегирует в send_local_file.
        """
        return self.send_local_file(relative_path, mimetype=mimetype)

    def get_path(self, relative_path: str) -> str:
        """Абсолютный путь к файлу по его относительному пути."""
        return self._safe_join(relative_path)

    def exists(self, relative_path: str) -> bool:
        """Проверка существования файла по относительному пути."""
        return os.path.exists(self._safe_join(relative_path))

    def delete(self, relative_path: str) -> bool:
        """
        Удаляет файл. Возвращает True, если файл был удалён, False — если не найден.
        """
        path = self._safe_join(relative_path)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def listdir(self, subdir: Optional[str] = None) -> List[str]:
        """
        Возвращает список файлов (именно файлов) в base_dir[/subdir]
        в виде относительных путей.
        """
        root = self._safe_join(subdir) if subdir else self.base_dir
        result: List[str] = []
        if not os.path.exists(root):
            return result
        for name in os.listdir(root):
            p = os.path.join(root, name)
            if os.path.isfile(p):
                # Относительный путь от base_dir
                result.append(os.path.relpath(p, self.base_dir))
        return result
