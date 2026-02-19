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
# gdal-bin и libgdal-dev нужны для работы сервиса ортофотопланов
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    ca-certificates \
    curl \
    libpq-dev \ 
 && rm -rf /var/lib/apt/lists/*

# Обязательные переменные окружения для компиляции Python-пакета GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Копируем requirements и устанавливаем их
COPY server/requirements.txt ./server/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r server/requirements.txt

# Устанавливаем Python-пакет GDAL строго той версии, которая стоит в системе
RUN pip install --no-cache-dir GDAL==$(gdal-config --version)

# Код бэкенда
# ВАЖНО: Убедитесь, что файл entrypoint.sh лежит в папке server на вашем компьютере, 
# чтобы он скопировался внутрь контейнера вместе с остальным кодом.
COPY server ./server

# Публичные файлы и сборка фронта
COPY public ./public
COPY --from=ui /ui/build ./public/build

# Создаем базовые папки (с запасом под разные пути из конфигов)
RUN mkdir -p /app/data /app/server/uploads /app/server/data/temp

# Создаем непривилегированного пользователя
RUN useradd -u 10001 -m appuser

# --- НОВЫЕ СТРОКИ ДЛЯ ENTRYPOINT ---
# Делаем скрипт исполняемым до того, как сменим права
RUN chmod +x /app/server/entrypoint.sh
# -----------------------------------

# Отдаем пользователю appuser права на ВСЮ папку /app
# Это гарантирует, что Flask/Gunicorn смогут создавать любые вложенные папки
RUN chown -R appuser:appuser /app

# Переключаемся на безопасного пользователя
USER appuser

EXPOSE 5000

# --- НОВЫЕ СТРОКИ ДЛЯ ENTRYPOINT ---
# Указываем скрипт инициализации как главную точку входа
ENTRYPOINT ["/app/server/entrypoint.sh"]
# -----------------------------------

CMD ["python", "server/app.py"]