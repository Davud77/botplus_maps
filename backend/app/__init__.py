from flask import Flask
from flask_cors import CORS
from .auth import login_blueprint
from .get_pano import pano_blueprint
from .upload_pano import upload_blueprint

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Регистрация всех Blueprints
    app.register_blueprint(login_blueprint)
    app.register_blueprint(pano_blueprint)
    app.register_blueprint(upload_blueprint)

    return app

app = create_app()
