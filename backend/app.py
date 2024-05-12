from flask import Flask
from flask_cors import CORS
from login import login_blueprint
from upload_pano import upload_blueprint
from get_pano import get_pano_blueprint

app = Flask(__name__)
CORS(app)

# Регистрация различных частей приложения как blueprint'ов
app.register_blueprint(login_blueprint, url_prefix='/api')
app.register_blueprint(upload_blueprint, url_prefix='/api')
app.register_blueprint(get_pano_blueprint, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True)
