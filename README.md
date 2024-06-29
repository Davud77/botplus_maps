npm install

cd frontend
npm start

cd backend
python app.py

git clone https://github.com/Davud77/panorama-viewer.git
cd panorama-viewer/backend
pip install flask-cors gunicorn psycopg2 minio Image piexif
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app

apt update
apt install python3-full python3-venv
python3 -m venv /usr/src/panorama-viewer-3/backend/venv
source /usr/src/panorama-viewer-3/backend/venv/bin/activate



Подключитесь к контейнеру базы данных:

sh
Copy code
docker exec -it panorama-viewer-3_db_1 bash
Запустите psql:

sh
Copy code
psql -U postgres
Создайте базу данных:

sql
Copy code
CREATE DATABASE botplus;