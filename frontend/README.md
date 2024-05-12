cd frontend
npm start

cd backend
python app.py
pip install flask-cors gunicorn psycopg2
gunicorn --workers 3 --bind 0.0.0.0:8000 app:app