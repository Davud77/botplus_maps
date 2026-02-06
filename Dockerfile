# ---------- 1) Сборка фронта (CRA) ----------
FROM node:22-alpine AS ui
WORKDIR /ui

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY tsconfig.json ./
COPY public ./public
COPY src ./src

# Фикс для некоторых версий npm/node
RUN npm install -D @babel/plugin-proposal-private-property-in-object \
 && npx update-browserslist-db@latest --yes || true

RUN npm run build

# ---------- 2) Runtime Flask ----------
FROM python:3.12-slim-bookworm AS runner

# Переменные для оптимизации Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Установка системных зависимостей
# libpq-dev нужен для psycopg2 (PostgreSQL)
# gdal-bin и libgdal-dev нужны только если вы используете GeoDjango или сложные гео-библиотеки.
# Для простого PostGIS через SQLAlchemy они обычно НЕ нужны, но я оставил их, чтобы не сломать вашу логику.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    gcc \
    ca-certificates \
    curl \
    libpq-dev \ 
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python зависимости
# ВАЖНО: В server/requirements.txt должны быть добавлены:
# minio
# psycopg2-binary
# GeoAlchemy2 (опционально, но удобно для PostGIS)
COPY server/requirements.txt ./server/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r server/requirements.txt

# Код бэкенда
COPY server ./server

# Публичные файлы и сборка фронта
COPY public ./public
COPY --from=ui /ui/build ./public/build

# Создаем папки для работы
RUN mkdir -p /app/data /app/server/uploads

# Создаем пользователя
RUN useradd -u 10001 -m appuser
# Меняем владельца папок, чтобы appuser мог в них писать
RUN chown -R appuser:appuser /app/data /app/server/uploads

USER appuser

EXPOSE 5000
CMD ["python", "server/app.py"]