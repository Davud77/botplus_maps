# server/controllers/ortho_controller.py
from flask import Blueprint, jsonify, request, make_response, send_file, abort, g
import import_jobs
from managers.ortho_manager import OrthoManager
from database import Database
from services.task_service import TaskService
from services.storage_service import StorageService
from services.gdal_service import GdalService
from services.ortho_service import OrthoService
import json
import os
from services.upload_names import ortho_upload_key

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
    def register_routes(blueprint, controller=None):
        c = controller if controller is not None else OrthoController()

        blueprint.add_url_rule("/orthophotos", view_func=c.get_orthophotos, methods=["GET"])
        blueprint.add_url_rule("/upload_ortho", view_func=c.upload_ortho, methods=["POST"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/process", view_func=c.process_ortho_cog, methods=["POST"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.get_ortho, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/download", view_func=c.download_ortho_file, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.update_ortho, methods=["PUT"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>", view_func=c.delete_ortho, methods=["DELETE"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>.png", view_func=c.get_ortho_tile, methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>@2x.png", endpoint="get_ortho_tile_2x", view_func=lambda ortho_id,z,x,y: c.get_ortho_tile(ortho_id,z,x,y,scale=2), methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/tiles/<int:z>/<int:x>/<int:y>@2x.webp", endpoint="get_ortho_tile_webp", view_func=lambda ortho_id,z,x,y: c.get_ortho_tile(ortho_id,z,x,y,scale=2,image_format='webp'), methods=["GET"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/reproject", view_func=c.reproject_ortho, methods=["POST"])
        blueprint.add_url_rule("/tasks/<task_id>", view_func=c.get_task_status, methods=["GET"])

        # [NEW] Маршруты для превью
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/generate_preview", view_func=c.generate_preview, methods=["POST"])
        blueprint.add_url_rule("/orthophotos/<int:ortho_id>/preview", view_func=c.download_ortho_preview, methods=["GET"])

    # --- Handlers ---

    def get_orthophotos(self):
        return jsonify(self.ortho_service.get_all()), 200

    def upload_ortho(self):
        # Compatibility endpoint: save/register only, without automatic preparation.
        from controllers.import_controller import upload
        return upload(field_name='files')

    def local_asset(self, ortho_id):
        return import_jobs.asset_record(ortho_id,self.db)

    def require_legacy(self,ortho_id):
        if self.local_asset(ortho_id): abort(409,description='Локальный слой уже подготовлен импортом. Для другой подготовки создайте новое задание; оригинал не меняется.')

    def process_ortho_cog(self, ortho_id):
        self.require_legacy(ortho_id)
        # 1. Проверяем состояние файла перед запуском
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho:
            return jsonify({"error": "Ortho not found"}), 404

        if getattr(ortho, 'is_cog', False):
            return jsonify({"error": "Файл уже является COG. Конвертация не требуется."}), 400

        # 2. Запускаем задачу
        task_id = self.ortho_service.start_cog_process(ortho_id)
        if not task_id:
            return jsonify({"error": "Не удалось запустить процесс"}), 500

        return jsonify({"task_id": task_id, "status": "started"}), 202

    def reproject_ortho(self, ortho_id):
        self.require_legacy(ortho_id)
        # 1. Проверяем проекцию файла перед запуском
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho:
            return jsonify({"error": "Ortho not found"}), 404

        crs = getattr(ortho, 'crs', '')
        if crs and ("3857" in crs or "Pseudo-Mercator" in crs or "Google" in crs):
            return jsonify({"error": "Файл уже находится в проекции Web Mercator (EPSG:3857)."}), 400

        # 2. Запускаем задачу
        task_id = self.ortho_service.start_reproject_process(ortho_id)
        if not task_id:
             return jsonify({"error": "Не удалось запустить процесс"}), 500

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
        asset=self.local_asset(ortho_id)
        if asset:
            try: path=import_jobs.asset_path(asset)
            except (ValueError,OSError): abort(409,description='Источник изменён или недоступен.')
            return send_file(path,as_attachment=True,download_name=ortho.filename)
        return self.storage_service.send_file(ortho.filename)

    # [NEW] Хендлеры для превью
    def generate_preview(self, ortho_id):
        self.require_legacy(ortho_id)
        task_id = self.ortho_service.start_preview_process(ortho_id)
        if not task_id:
            return jsonify({"error": "Ortho not found or failed to start"}), 404
        return jsonify({"task_id": task_id, "status": "started"}), 202

    def download_ortho_preview(self, ortho_id):
        ortho = self.ortho_manager.get_ortho_by_id(ortho_id)
        if not ortho or not getattr(ortho, 'preview_filename', None):
            return jsonify({"error": "Превью не найдено"}), 404
        return self.storage_service.send_file(ortho.preview_filename)

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

        if self.local_asset(ortho_id):
            with self.db.cursor(write=True) as cur:
                cur.execute('DELETE FROM import_assets WHERE ortho_id=%s',(ortho_id,))
                cur.execute('DELETE FROM raster_sources WHERE ortho_id=%s',(ortho_id,))
                cur.execute('DELETE FROM orthophotos WHERE id=%s',(ortho_id,))
            return jsonify(status='success',message='Регистрация удалена; исходный файл сохранён.'),200

        # [UPDATED] Удаляем также и файл превью, если он есть
        self.storage_service.delete_file(ortho.filename)
        if getattr(ortho, 'preview_filename', None):
            self.storage_service.delete_file(ortho.preview_filename)

        self.ortho_manager.delete_ortho(ortho_id)
        return jsonify({"status": "success"}), 200

    def get_ortho_tile(self, ortho_id, z, x, y, scale=1, image_format='png'):
        options={'scale':scale}
        if image_format!='png':options['image_format']=image_format
        content = self.ortho_service.proxy_tile(ortho_id, z, x, y, **options)
        if not content:
             return jsonify({"error": "Raster tile unavailable"}), 502

        response = make_response(content)
        response.headers.set("Content-Type", "image/webp" if image_format=='webp' else "image/png")
        response.headers.set("Cache-Control", "private, max-age=60")
        response.headers["X-Raster-Cache"]=getattr(g,"raster_cache","BYPASS")
        response.headers["Server-Timing"]=getattr(g,"raster_server_timing","")
        return response

    def get_task_status(self, task_id):
        from uuid import UUID
        from flask import g
        try:
            identifier=str(UUID(task_id))
        except ValueError:
            identifier=None
        if identifier:
            with self.db.cursor() as cur:
                cur.execute('SELECT * FROM import_jobs WHERE id=%s',(identifier,))
                row=cur.fetchone()
            if row:
                if row['owner_id']!=g.current_user_id and g.current_user['role']!='admin': abort(404)
                return jsonify(status={'queued':'pending','running':'processing','succeeded':'success','failed':'error','cancelled':'error'}[row['status']],progress=row['progress'],message=row['message'],error=row['error'] or row['message']),200
        state = self.task_service.get_state(task_id)
        if not state:
            return jsonify({"status": "not_found"}), 404
        return jsonify(state), 200

# Регистрация
def create_ortho_blueprint(controller=None):
    blueprint = Blueprint("ortho", __name__)
    OrthoController.register_routes(blueprint, controller)
    return blueprint
