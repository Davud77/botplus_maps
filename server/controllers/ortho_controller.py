from flask import Blueprint, jsonify, request, make_response
from managers.ortho_manager import OrthoManager
from database import Database
from services.task_service import TaskService
from services.storage_service import StorageService
from services.gdal_service import GdalService
from services.ortho_service import OrthoService
import json

ortho_blueprint = Blueprint("ortho", __name__)

class OrthoController:
    def __init__(self):
        # Инициализация зависимостей
        self.db = Database()
        self.ortho_manager = OrthoManager(self.db)
        
        # Сервисы
        self.task_service = TaskService()
        self.storage_service = StorageService()
        self.gdal_service = GdalService()
        
        # Оркестратор
        self.ortho_service = OrthoService(
            self.db, 
            self.ortho_manager, 
            self.storage_service, 
            self.gdal_service, 
            self.task_service
        )

    @staticmethod
    def register_routes(blueprint):
        c = OrthoController()

        blueprint.add_url_rule("/orthophotos", view_func=c.get_orthophotos, methods=["GET"])
        blueprint.add_url_rule("/upload_ortho", view_func=c.upload_ortho, methods=["POST"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/process", view_func=c.process_ortho_cog, methods=["POST"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.get_ortho, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/download", view_func=c.download_ortho_file, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.update_ortho, methods=["PUT"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.delete_ortho, methods=["DELETE"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>.png", view_func=c.get_ortho_tile, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/reproject", view_func=c.reproject_ortho, methods=["POST"])
        blueprint.add_url_rule("/tasks/<task_id>", view_func=c.get_task_status, methods=["GET"])

    # --- Handlers ---

    def get_orthophotos(self):
        return jsonify(self.ortho_service.get_all()), 200

    def upload_ortho(self):
        files = request.files.getlist("files")
        if not files:
            return jsonify({"message": "Нет файлов"}), 400
        
        success, failed, logs = self.ortho_service.handle_upload(files)
        return jsonify({
            "message": "Загрузка завершена",
            "successful_uploads": success,
            "failed_uploads": failed,
            "logs": logs
        }), 200

    def process_ortho_cog(self, ortho_id):
        task_id = self.ortho_service.start_cog_process(ortho_id)
        if not task_id:
            return jsonify({"error": "Ortho not found"}), 404
        return jsonify({"task_id": task_id, "status": "started"}), 202

    def reproject_ortho(self, ortho_id):
        task_id = self.ortho_service.start_reproject_process(ortho_id)
        if not task_id:
            return jsonify({"error": "Ortho not found"}), 404
        return jsonify({"task_id": task_id, "status": "started"}), 202

    def get_ortho(self, ortho_id):
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho:
            return jsonify({"error": "Not found"}), 404
        
        b = json.loads(ortho.bounds) if ortho.bounds else None
        return jsonify({
            "id": ortho.id,
            "filename": ortho.filename,
            "url": f"/api/orthophotos/{ortho.id}/download",
            "bounds": b,
            "crs": getattr(ortho, 'crs', None),
            "is_visible": getattr(ortho, 'is_visible', False)
        }), 200

    def download_ortho_file(self, ortho_id):
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho:
            return jsonify({"error": "Not found"}), 404
        return self.storage_service.send_file(ortho.filename)

    def update_ortho(self, ortho_id):
        try:
            self.ortho_manager.update_ortho(ortho_id, request.json)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def delete_ortho(self, ortho_id):
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho:
            return jsonify({"error": "Not found"}), 404
        
        self.storage_service.delete_file(ortho.filename)
        self.ortho_manager.delete_ortho(ortho_id)
        return jsonify({"status": "success"}), 200

    def get_ortho_tile(self, ortho_id, z, x, y):
        content = self.ortho_service.proxy_tile(ortho_id, z, x, y)
        if not content:
             return jsonify({"error": "Failed"}), 404
             
        response = make_response(content)
        response.headers.set("Content-Type", "image/png")
        response.headers.set("Cache-Control", "public, max-age=3600")
        return response

    def get_task_status(self, task_id):
        state = self.task_service.get_state(task_id)
        if not state:
            return jsonify({"status": "not_found"}), 404
        return jsonify(state), 200

# Регистрация
OrthoController.register_routes(ortho_blueprint)