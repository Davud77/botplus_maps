# ./backend/storage.py

import os
from flask import send_file, jsonify
import io

class LocalStorage:
    """
    Класс для локального хранения файлов (загрузка, скачивание).
    """
    def __init__(self, base_folder):
        self.base_folder = base_folder

    def save_file(self, file_stream, filename):
        if not os.path.exists(self.base_folder):
            os.makedirs(self.base_folder, exist_ok=True)
        file_path = os.path.join(self.base_folder, filename)
        file_stream.seek(0)
        with open(file_path, "wb") as f:
            f.write(file_stream.read())
        return file_path

    def send_local_file(self, filename, mimetype='application/octet-stream'):
        file_path = os.path.join(self.base_folder, filename)
        if os.path.exists(file_path):
            return send_file(file_path, mimetype=mimetype, download_name=filename)
        else:
            return jsonify({"error": "File not found"}), 404

    def get_local_file_path(self, filename):
        return os.path.join(self.base_folder, filename)