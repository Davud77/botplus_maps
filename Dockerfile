# ---------- 1) Сборка фронта (CRA/React) ----------
FROM node:22-alpine AS ui
WORKDIR /ui

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY tsconfig.json ./
COPY public ./public
COPY src ./src

# Небольшие улучшения совместимости браузеров
RUN npm install -D @babel/plugin-proposal-private-property-in-object \
 && npx update-browserslist-db@latest --yes || true

RUN npm run build


# ---------- 2) Runtime Flask ----------
FROM python:3.12-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Минимум системных пакетов (curl для healthcheck)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python зависимости
COPY server/requirements.txt ./server/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r ./server/requirements.txt

# Код бэкенда
COPY server ./server

# Публичные файлы и готовая сборка фронта
COPY public ./public
COPY --from=ui /ui/build ./public/build

# Рабочие каталоги (персистентный /app/data пробрасывается томом через compose)
RUN mkdir -p /app/data \
             /app/server/uploads/panos \
             /app/server/uploads/orthos/tiles

# Непривилегированный пользователь
RUN useradd -u 10001 -m appuser
USER appuser

# Экспонируем API/SPA
EXPOSE 5000

# Запуск продакшен-сервера на фабрике приложения (app:create_app())
WORKDIR /app/server
CMD ["gunicorn", "--workers", "3", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:create_app()"]
