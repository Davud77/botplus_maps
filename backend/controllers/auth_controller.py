from flask import Blueprint, request, jsonify, session, make_response
from flask_cors import cross_origin
from managers.user_manager import UserManager
from database import Database
from werkzeug.security import check_password_hash

auth_blueprint = Blueprint("auth", __name__)

class AuthController:
    def __init__(self):
        self.db = Database()
        self.user_manager = UserManager(self.db)

    @staticmethod
    def register_routes(blueprint):
        controller = AuthController()
        blueprint.add_url_rule("/login", view_func=controller.login, methods=["POST"])
        blueprint.add_url_rule("/register", view_func=controller.register, methods=["POST"])

    @cross_origin(origins="http://localhost:3000", supports_credentials=True)
    def login(self):
        try:
            data = request.json
            username = data.get("username")
            password = data.get("password")

            user = self.user_manager.find_by_username(username)
            if user and check_password_hash(user.password, password):
                # Сохраняем данные в сессии
                session['user_id'] = user.id
                session['username'] = user.username

                # Формируем ответ с куками
                resp = make_response(jsonify({"status": "success", "message": "Login successful"}), 200)
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                return resp
            else:
                return jsonify({"status": "fail", "message": "Invalid username or password"}), 401
        except Exception as e:
            print(f"Ошибка при авторизации: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @cross_origin(origins="http://localhost:3000", supports_credentials=True)
    def register(self):
        """
        Регистрация нового пользователя.
        Ожидается JSON: {"username": "...", "password": "..."}
        """
        try:
            data = request.json
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                return jsonify({"status": "fail", "message": "Username and password are required"}), 400

            # Проверяем, нет ли пользователя с таким именем
            existing_user = self.user_manager.find_by_username(username)
            if existing_user:
                return jsonify({"status": "fail", "message": "User already exists"}), 400

            # Создаём пользователя
            self.user_manager.create_user(username, password)
            return jsonify({"status": "success", "message": "User registered successfully"}), 201
        except Exception as e:
            print(f"Ошибка при регистрации: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

# Регистрация роутов
AuthController.register_routes(auth_blueprint)