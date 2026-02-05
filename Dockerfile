# ---------- 1) Сборка фронта (CRA) ----------
FROM node:22-alpine AS ui
WORKDIR /ui

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY tsconfig.json ./
COPY public ./public
COPY src ./src

RUN npm install -D @babel/plugin-proposal-private-property-in-object \
 && npx update-browserslist-db@latest --yes || true

RUN npm run build

# ---------- 2) Runtime Flask ----------
FROM python:3.12-slim-bookworm AS runner
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# ! ВАЖНО: Добавлен libpq-dev для работы psycopg2 (PostgreSQL драйвер)
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
COPY server/requirements.txt ./server/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r server/requirements.txt

# Код бэкенда
COPY server ./server

# Публичные файлы и сборка фронта
COPY public ./public
COPY --from=ui /ui/build ./public/build

# Рабочие каталоги
RUN mkdir -p /app/data /app/server/uploads

# Запуск под непривилегированным пользователем
RUN useradd -u 10001 -m appuser
USER appuser

# DB_FILE больше не нужен как основной источник, но можно оставить для легаси
ENV DB_FILE=/app/data/botplus.db
EXPOSE 5000
CMD ["python", "server/app.py"]