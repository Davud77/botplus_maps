FROM python:3.10-slim

# Install system dependencies for GDAL and build tools
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    build-essential \
    && apt-get clean

# Set environment variables for GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt requirements.txt

# Upgrade pip and install Python packages
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run.py"]
