FROM python:3.8-slim
WORKDIR /app
COPY . /app
RUN pip install flask psycopg2-binary flask-cors minio Pillow piexif
EXPOSE 5000
CMD ["python", "app.py"]
