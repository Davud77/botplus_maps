from flask import Flask, request
from flask_cors import CORS
import config

# Импортируем блюпринты
from controllers.auth_controller import auth_blueprint
from controllers.pano_controller import pano_blueprint
from controllers.ortho_controller import ortho_blueprint

def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # Конфигурация куки для всех поддоменов
    app.config.update(
        SESSION_COOKIE_DOMAIN='.botplus.ru',
        SESSION_COOKIE_SAMESITE='None',
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True
    )

    # Настройка CORS
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3080",
        "https://botplus.ru",
        "https://api.botplus.ru",
        "https://*.botplus.ru"
    ]

    CORS(
        app,
        resources={r"/*": {"origins": allowed_origins}},
        supports_credentials=True,
        expose_headers=['Content-Type', 'Authorization'],
        allow_headers=['Content-Type', 'Authorization']
    )

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        return response

    # Регистрация блюпринтов
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(pano_blueprint)
    app.register_blueprint(ortho_blueprint)

    return app

if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=False)