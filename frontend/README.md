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
