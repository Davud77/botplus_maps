from flask import Flask
from flask_cors import CORS
from login import login_blueprint  # Убедитесь, что правильно импортировали Blueprint

app = Flask(__name__)
CORS(app)

# Регистрация Blueprint
app.register_blueprint(login_blueprint)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)  # host и port необязательны, если вы используете Gunicorn
