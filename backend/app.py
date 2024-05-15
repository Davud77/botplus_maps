from flask import Flask
from flask_cors import CORS
from login import login_blueprint
from get_pano import pano_blueprint
from upload_pano import upload_blueprint  # Предполагая, что у вас есть upload.py преобразованный в Blueprint

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Разрешить все домены, либо укажите конкретные

# Регистрация всех Blueprints
app.register_blueprint(login_blueprint)
app.register_blueprint(pano_blueprint)
app.register_blueprint(upload_blueprint)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
