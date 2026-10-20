> **Self-host rebuild started on 21 October 2026.** The original setup documentation below describes the legacy application. Start with the [roadmap and release gates](ROADMAP.md), [architecture decision](docs/architecture/0001-self-host-data-and-ingestion.md), [local raster tools](docs/LOCAL_IMPORT.md), and [current security limitations](SECURITY.md). No-copy disk/NAS import and resumable uploads are planned; the first CLI currently performs metadata inspection only.

```markdown
# Botplus Maps (GIS Platform)

Полная документация проекта: микросервисная архитектура, работа с PostGIS/MinIO, API векторных тайлов и инструкция по развертыванию.

---

## 🔎 Что это такое

**Botplus Maps** — профессиональная веб-платформа для работы с геопространственными данными. Система позволяет объединять на одной карте векторные слои, ортофотопланы (COG) и сферические панорамы 360°.

Проект построен на современном стеке с использованием **Docker-оркестрации**:
* **Фронтенд**: React + TypeScript (CRA), стейт-менеджер **Zustand**, картографический движок **Leaflet**.
* **Бэкенд**: Flask (Python 3.12) со слоистой архитектурой (**Controllers → Managers → Services → Repositories**).
* **Инфраструктура данных**:
    * 🐘 **PostgreSQL 16 + PostGIS 3.4** — хранение векторной геометрии и метаданных.
    * 🗄️ **MinIO (S3)** — объектное хранилище для панорам и GeoTIFF.
    * 🌍 **TiTiler** — динамический тайловый сервер для рендеринга COG.
    * ⚡ **PgBouncer** — пулер соединений для высокой нагрузки.

### Ключевые возможности:
* 🔑 **Безопасность**: Кастомная JWT-аутентификация через HttpOnly cookies.
* 📐 **Векторные карты**: Генерация MVT (Mapbox Vector Tiles) на лету из PostGIS с поддержкой динамической стилизации.
* 🖼️ **Панорамы 360°**: Массовая загрузка, парсинг EXIF (GPS/Heading), кластеризация маркеров на карте, просмотр через Marzipano.
* 🦅 **Ортофото**: Загрузка GeoTIFF, автоматическое извлечение границ (GDAL) и стриминг тайлов через TiTiler.
* 🚀 **Масштабируемость**: Полная контейнеризация всех компонентов через Docker Compose.

Публичный API (в проде): `https://api.botplus.ru` (пример).

---

## 📦 Структура репозитория



.
├── data/
│   ├── minio_data/               # Данные объектного хранилища (если используется MinIO)
│   └── pg_data/                  # Персистентные данные PostgreSQL
├── pgbouncer/                    # Конфигурация пулера соединений БД
│   ├── pgbouncer.ini
│   └── userlist.txt
├── public/                       # Статические ассеты фронтенда
│   ├── icons/
│   ├── images/
│   ├── videos/
│   ├── favicon.ico
│   ├── index.html
│   └── manifest.json
├── server/                       # Backend (Flask)
│   ├── alembic/                  # Миграции базы данных
│   ├── app/
│   │   └── routers/              # Доп. роуты (FastAPI/Flask style)
│   ├── controllers/              # Входные точки API (Blueprints)
│   │   ├── auth_controller.py
│   │   ├── ortho_controller.py
│   │   ├── pano_controller.py
│   │   └── vector.py             # Контроллер векторных данных
│   ├── managers/                 # Бизнес-логика (фасады)
│   │   ├── ortho_manager.py
│   │   ├── pano_manager.py
│   │   └── user_manager.py
│   ├── models/                   # SQLModels / SQLAlchemy модели
│   │   ├── ortho.py
│   │   ├── pano.py
│   │   └── user.py
│   ├── repositories/             # Слой работы с БД (CRUD)
│   │   └── user_repository.py
│   ├── services/                 # Сервисные функции и утилиты
│   │   ├── uploads/
│   │   └── auth_service.py
│   ├── app.py                    # Точка входа приложения
│   ├── config.py                 # Конфигурация приложения
│   ├── database.py               # Подключение к БД
│   ├── init_db.py                # Инициализация БД
│   ├── init_pg_auth.py           # Инициализация аутентификации PG
│   ├── reset_pass.py             # Скрипт сброса паролей
│   ├── storage.py                # Работа с файловой системой/S3
│   └── requirements.txt          # Python-зависимости
├── src/                          # Frontend (React)
│   ├── components/
│   │   ├── maps/
│   │   │   ├── core/             # Ядро карты (события, контролы)
│   │   │   ├── hooks/            # Хуки состояния (Zustand/Context)
│   │   │   │   ├── useMapStore.ts
│   │   │   │   ├── useUIStore.ts
│   │   │   │   └── useVectorStore.ts
│   │   │   ├── layers/           # Реализация слоев (Ortho, Pano, Vector)
│   │   │   └── ui/               # Элементы интерфейса карты
│   │   │       ├── panels/       # Боковые панели управления
│   │   │       └── viewers/      # Вьювер панорам
│   │   ├── profile/              # Личный кабинет пользователя
│   │   │   ├── ProfileDashboard.tsx
│   │   │   ├── ProfileOrthophotos.tsx
│   │   │   ├── ProfilePanoramas.tsx
│   │   │   └── ProfileVector.tsx
│   │   ├── Header.tsx
│   │   ├── Home.tsx
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── UploadOrtho.tsx
│   │   └── UploadPano.tsx
│   ├── contexts/                 # React Context (Auth)
│   ├── hooks/                    # Общие хуки (useAuth)
│   ├── types/                    # TypeScript определения (.d.ts)
│   ├── utils/                    # Утилиты (API wrapper)
│   ├── App.tsx
│   ├── index.tsx
│   ├── routes.tsx
│   └── setupProxy.js             # Прокси для разработки
├── .env                          # Переменные окружения (не в git)
├── docker-compose.yml            # Оркестрация контейнеров
├── Dockerfile                    # Сборка образа
├── package.json                  # JS-зависимости
├── tsconfig.json                 # Конфигурация TS
└── README.md



> Важно: вся прикладная логика — на сервере (валидация, правила, права). На фронте — только отображение и вызовы API.

---





Отлично, обновляем технические разделы. Поскольку архитектура изменилась с локального SQLite на кластер (PostGIS + MinIO + TiTiler), эти секции требуют полного переписывания.

Вот обновленный текст для `README.md`, охватывающий новую схему БД, расширенные переменные окружения и гибридный запуск.

---

## 🧰 Схема базы данных

Проект использует **PostgreSQL 16** с расширением **PostGIS 3.4**.

### Основные таблицы

```sql
-- Пользователи (Auth)
-- Создается автоматически: init_pg_auth.py
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    username   VARCHAR(50) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL, -- Scrypt/PBKDF2 хеш
    created_at TIMESTAMP DEFAULT NOW()
);

-- Панорамы (GIS Data)
-- Таблица 'photos_4326' для работы с геометрией
CREATE TABLE IF NOT EXISTS public.photos_4326 (
    id          SERIAL PRIMARY KEY,
    geom        GEOMETRY(Point, 4326), -- PostGIS точка (lon, lat)
    filename    TEXT,                  -- Имя файла в MinIO
    path        TEXT,                  -- Полный путь
    directory   TEXT,
    timestamp   TIMESTAMP,             -- EXIF Date
    altitude    FLOAT,                 -- Высота над уровнем моря
    direction   FLOAT,                 -- Направление камеры (Heading)
    rotation    FLOAT,                 -- Roll
    "order"     INTEGER
);

-- Ортофотопланы (Raster Metadata)
CREATE TABLE IF NOT EXISTS orthophotos (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,         -- Имя файла в MinIO (bucket: orthophotos)
    bounds      TEXT,                  -- JSON {north, south, east, west}
    url         TEXT,                  -- Ссылка (опционально)
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

> **Важно:** База данных инициализируется скриптом `server/init_pg_auth.py`, который создает дефолтного администратора: `admin` / `admin`.

---

## ⚙️ Переменные окружения

Настройки вынесены в `docker-compose.yml` и `config.py`.

### Backend (Flask)

| Переменная | Описание | Значение по умолчанию (Docker) |
| --- | --- | --- |
| `DATABASE_URL` | Строка подключения к PG (обычно через PgBouncer) | `postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db` |
| `MINIO_ENDPOINT` | Хост S3-хранилища | `minio:9000` |
| `MINIO_ACCESS_KEY` | Логин S3 | `minioadmin` |
| `MINIO_SECRET_KEY` | Пароль S3 | `minioadmin` |
| `MINIO_SECURE` | Использовать ли HTTPS для S3 | `False` |
| `JWT_SECRET` | Секрет для подписи токенов | `change-me` |
| `UPLOAD_FOLDER` | Временная папка для загрузок | `/app/server/uploads` |

### Frontend (Build time)

Проект настроен на автоматическое определение API.

* **Local Development**: Запросы проксируются через `src/setupProxy.js` на `:5000`.
* **Production**: Используются относительные пути (`/api/...`).

### TiTiler (GeoTIFF Server)

| Переменная | Зачем нужна |
| --- | --- |
| `AWS_S3_ENDPOINT` | Указывает GDAL ходить в наш локальный MinIO (`minio:9000`) |
| `AWS_HTTPS` | `FALSE` (отключает SSL handshake для внутреннего трафика) |
| `AWS_VIRTUAL_HOSTING` | `FALSE` (использует path-style access `host/bucket/file`) |

---

## 🧑‍💻 Запуск в разработке (Гибридный режим)

Так как поднять PostGIS и MinIO локально "руками" сложно, рекомендуется гибридный подход: **Инфраструктура в Docker**, а **Код локально**.

### Шаг 1: Инфраструктура

Запустите только базы данных и вспомогательные сервисы:

```bash
docker compose up -d db minio pgbouncer titiler

```

*Убедитесь, что порты `5432`, `9000`, `9001`, `6432` свободны.*

### Шаг 2: Backend (Python)

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)

# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка ENV для локального запуска (переопределяем Docker-хосты на localhost)
export DATABASE_URL="postgresql://botplus_user:botplus_password@localhost:6432/botplus_db"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_SECURE="False"
export UPLOAD_FOLDER="./uploads"  # Создайте эту папку

# 3. Инициализация БД (если первый раз)
python init_pg_auth.py

# 4. Запуск
python app.py

```

*Сервер запустится на `http://127.0.0.1:5000`.*

### Шаг 3: Frontend (React)

```bash
# В корне проекта
npm install
npm start

```

*Фронтенд запустится на `http://localhost:3000`. Благодаря `setupProxy.js`, запросы `/api` будут улетать на ваш локальный Python-сервер.*






Продолжаем обновление. Следующие разделы (Docker, Production, API, Frontend) кардинально изменились из-за внедрения микросервисов (MinIO, PostGIS, TiTiler).

Скопируйте этот блок и вставьте его **после** раздела "Запуск в разработке":

---

## 🐳 Запуск в Docker (Рекомендуемый)

Проект использует сложную оркестрацию из 5 сервисов. Ручной запуск через `docker run` не рекомендуется.

### Docker Compose

```bash
# 1. Сборка и запуск в фоновом режиме
docker compose up -d --build

# 2. Просмотр логов (чтобы убедиться, что БД инициализировалась)
docker compose logs -f app

```

**Сервисы в стеке:**

1. **`app`** (:5580) — Основное приложение (Flask + React Static).
2. **`db`** (:5432) — PostgreSQL 16 + PostGIS 3.4.
3. **`minio`** (:9000, :9001) — S3-хранилище файлов.
4. **`pgbouncer`** (:6432) — Пулер соединений для БД.
5. **`titiler`** (:8000) — Сервер рендеринга GeoTIFF (COG).

> **Healthcheck:** При первом запуске скрипт `init_pg_auth.py` может ждать готовности БД до 30 секунд.

---

## 🚀 Продакшн (Deploy)

Контейнер `app` уже запускается через **Gunicorn** с поддержкой **Gevent** (см. `docker-compose.yml` -> `command`).
Вам нужно лишь настроить **Nginx** как реверс-прокси перед Docker-портом `5580`.

**Пример конфигурации Nginx (`/etc/nginx/sites-available/botplus`):**

```nginx
server {
    server_name maps.yourdomain.com;

    # Лимит на загрузку больших GeoTIFF/Панорам
    client_max_body_size 500M;

    location / {
        # Проксируем на порт Docker-контейнера (5580)
        proxy_pass http://127.0.0.1:5580;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Для поддержки долгих запросов (загрузка файлов)
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
    
    # (Опционально) SSL через Certbot
    # listen 443 ssl...
}

```

---

## 🧭 API (Справочник)

Все эндпоинты имеют префикс `/api`.

### 🔐 Аутентификация (Custom JWT)

*Токены хранятся в HttpOnly Cookie.*

* `POST /api/auth/login` — Вход `{username, password}`.
* `GET /api/auth/me` — Проверка сессии. Возвращает `{authenticated: true, user: {...}}`.
* `POST /api/auth/logout` — Очистка куки.

### 📐 Векторные данные (PostGIS)

* `GET /api/vector/databases` — Список подключенных баз.
* `GET /api/vector/layers/{db_name}` — Список таблиц с геометрией.
* `GET /api/vector/tiles/combined/{db}/{z}/{x}/{y}.pbf` — **MVT Тайлы**. Динамическая генерация Mapbox Vector Tiles из PostGIS.
* `GET /api/vector/styles/{db}/{schema}/{table}` — Получение стилей слоя (Single/Categorized).

### 📷 Панорамы 360°

* `GET /api/panoramas` — Список панорам (поддерживает BBOX фильтрацию).
* `POST /api/upload` — Загрузка (Multipart). Извлекает EXIF, сохраняет в MinIO + PostGIS.

### 🦅 Ортофотопланы

* `GET /api/orthophotos` — Список загруженных карт.
* `POST /api/upload_ortho` — Загрузка GeoTIFF. Файл сохраняется в MinIO, границы вычисляются через GDAL.

---

## 🖥️ Фронтенд (Архитектура)

Структура `src/components/maps` полностью модульная:

* **State Management (Zustand)**:
* `useMapStore.ts` — Состояние растровых слоев (Орто).
* `useVectorStore.ts` — Кэш векторных данных и стилей.
* `useUIStore.ts` — Управление панелями (Layers, Pano, Vector).


* **Слои (`layers/`)**:
* `VectorLayerRenderer` — Умный рендеринг MVT через `leaflet.vectorgrid`.
* `OrthoLayer` — Формирует ссылки на TiTiler.
* `PanoLayer` — Кластеризация маркеров.


* **Core**:
* `CustomZoomControl` — Кастомные кнопки зума.
* `MapEvents` — Обработка кликов и контекстного меню.



---

## 🧯 Troubleshooting

### 1. Ошибка "MinIO Connection Refused"

Если TiTiler или Backend не видят MinIO:

* Проверьте, что все сервисы в одной сети (docker network).
* В `docker-compose.yml` проверьте переменные `MINIO_ENDPOINT` (должно быть `minio:9000`, а не localhost).

### 2. Не грузятся тайлы карты (404/500)

* **Vector**: Убедитесь, что в таблице PostGIS есть геометрия и SRID=4326. Проверьте логи `app` на ошибки SQL.
* **Ortho**: Откройте консоль браузера (Network). Если ошибка от TiTiler, проверьте логи контейнера `titiler`. Возможно, он не может скачать файл из MinIO из-за настроек региона/бакета.

### 3. "Index.html not found"

* Убедитесь, что Docker-образ собрался корректно. Frontend билдится на этапе `FROM node:22-alpine AS ui`. Проверьте наличие папки `/app/public/build` внутри контейнера.

---

## 🧪 Быстрые команды

```bash
# 🔥 Полный перезапуск (с пересборкой)
docker compose down
docker compose up -d --build

# 📜 Чтение логов бэкенда
docker compose logs -f app

# 🗑️ Очистка базы данных (Удаление томов!)
docker compose down -v

```

---

## 📜 Лицензия

© Botplus Maps. Enterprise GIS Solution.


































































Вот полный, обновленный файл `README.md`, собранный в единый документ. Он учитывает все изменения архитектуры (PostGIS, MinIO, TiTiler, Microservices), которые мы проанализировали в ваших файлах.

```markdown
# Botplus Maps (Enterprise GIS Platform)

Полная документация проекта: микросервисная архитектура, работа с PostGIS/MinIO, API векторных тайлов и инструкция по развертыванию.

---

## 🔎 Что это такое

**Botplus Maps** — профессиональная веб-платформа для работы с геопространственными данными. Система позволяет объединять на одной карте векторные слои, ортофотопланы (COG) и сферические панорамы 360°.

Проект построен на современном стеке с использованием **Docker-оркестрации**:
* **Фронтенд**: React + TypeScript (CRA), стейт-менеджер **Zustand**, картографический движок **Leaflet**.
* **Бэкенд**: Flask (Python 3.12) со слоистой архитектурой (**Controllers → Managers → Services → Repositories**).
* **Инфраструктура данных**:
    * 🐘 **PostgreSQL 16 + PostGIS 3.4** — хранение векторной геометрии и метаданных.
    * 🗄️ **MinIO (S3)** — объектное хранилище для панорам и GeoTIFF.
    * 🌍 **TiTiler** — динамический тайловый сервер для рендеринга COG (Cloud Optimized GeoTIFF).
    * ⚡ **PgBouncer** — пулер соединений для высокой нагрузки.

### Ключевые возможности:
* 🔑 **Безопасность**: Кастомная JWT-аутентификация через HttpOnly cookies.
* 📐 **Векторные карты**: Генерация MVT (Mapbox Vector Tiles) на лету из PostGIS с поддержкой динамической стилизации (Simple/Categorized).
* 🖼️ **Панорамы 360°**: Массовая загрузка, парсинг EXIF (GPS/Heading), кластеризация маркеров на карте, просмотр через Marzipano.
* 🦅 **Ортофото**: Загрузка GeoTIFF, автоматическое извлечение границ (GDAL) и стриминг тайлов через TiTiler.
* 🚀 **Масштабируемость**: Полная контейнеризация всех компонентов через Docker Compose.

Публичный API (в проде): `https://api.botplus.ru` (пример).

---

## 📦 Структура репозитория

```text
.
├── data/                         # Persisted Data (Docker volumes)
│   ├── minio_data/               # Данные S3 (панорамы, ортофото)
│   └── pg_data/                  # Файлы базы данных PostgreSQL
├── pgbouncer/                    # Конфигурация пулера соединений
│   ├── pgbouncer.ini
│   └── userlist.txt
├── server/                       # Backend (Flask Application)
│   ├── alembic/                  # Миграции базы данных
│   ├── app/
│   │   └── routers/              # Доп. роуты
│   ├── controllers/              # API Endpoints (Blueprints)
│   │   ├── auth_controller.py    # Логин/Регистрация/Me
│   │   ├── ortho_controller.py   # Ортофотопланы
│   │   ├── pano_controller.py    # Панорамы 360
│   │   └── vector.py             # Генерация MVT тайлов из PostGIS
│   ├── managers/                 # Бизнес-логика (Orchestration)
│   │   ├── ortho_manager.py
│   │   ├── pano_manager.py
│   │   └── user_manager.py
│   ├── models/                   # Модели данных
│   │   ├── ortho.py
│   │   ├── pano.py
│   │   └── user.py
│   ├── repositories/             # Слой работы с БД (SQL/CRUD)
│   │   └── user_repository.py
│   ├── services/                 # Внешние сервисы
│   │   └── auth_service.py       # JWT Logic
│   ├── app.py                    # Точка входа Flask & Serve Static
│   ├── config.py                 # Конфигурация (ENV vars)
│   ├── database.py               # Подключение к БД (через PgBouncer)
│   ├── init_pg_auth.py           # Инициализация схемы БД
│   ├── storage.py                # Wrapper для MinIO и LocalStorage
│   └── requirements.txt          # Python-зависимости
├── src/                          # Frontend (React + TypeScript)
│   ├── components/
│   │   ├── maps/
│   │   │   ├── core/             # Ядро карты (Zoom, Events)
│   │   │   ├── hooks/            # Zustand Stores (Map, UI, Vector)
│   │   │   ├── layers/           # Реализация слоев (Ortho, Pano, VectorTile)
│   │   │   └── ui/               # Интерфейс карты
│   │   │       ├── panels/       # Боковые панели
│   │   │       └── viewers/      # PanoramaViewer (Marzipano)
│   │   ├── profile/              # Личный кабинет (Dashboard)
│   │   └── ...
│   ├── contexts/                 # React Context (Auth)
│   ├── utils/                    # API wrappers (axios/fetch)
│   ├── App.tsx                   # Роутинг
│   └── setupProxy.js             # Прокси для разработки
├── .env                          # Переменные окружения (не в git)
├── docker-compose.yml            # Оркестрация контейнеров
└── Dockerfile                    # Multi-stage сборка

```

> **Важно:** Вся прикладная логика — на сервере. Фронтенд отвечает только за отображение и вызовы API.

---

## 🧰 Схема базы данных

Проект использует **PostgreSQL 16** с расширением **PostGIS 3.4**.

### Основные таблицы

```sql
-- Пользователи (Auth)
-- Инициализация: server/init_pg_auth.py
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    username   VARCHAR(50) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL, -- Scrypt/PBKDF2 хеш
    created_at TIMESTAMP DEFAULT NOW()
);

-- Панорамы (GIS Data)
-- Таблица 'photos_4326' хранит геометрию Point(lon, lat)
CREATE TABLE IF NOT EXISTS public.photos_4326 (
    id          SERIAL PRIMARY KEY,
    geom        GEOMETRY(Point, 4326), -- PostGIS Geometry
    filename    TEXT,                  -- Имя файла в MinIO
    path        TEXT,
    directory   TEXT,
    timestamp   TIMESTAMP,             -- EXIF Date
    altitude    FLOAT,                 -- Высота над уровнем моря
    direction   FLOAT,                 -- Направление камеры (Heading)
    rotation    FLOAT,                 -- Roll
    "order"     INTEGER
);

-- Ортофотопланы (Raster Metadata)
CREATE TABLE IF NOT EXISTS orthophotos (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,         -- Имя файла в MinIO (bucket: orthophotos)
    bounds      TEXT,                  -- JSON {north, south, east, west}
    url         TEXT,                  -- Ссылка (опционально)
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

> **Важно:** База данных инициализируется скриптом `server/init_pg_auth.py`, который создает дефолтного администратора: `admin` / `admin`.

---

## ⚙️ Переменные окружения

Настройки вынесены в `docker-compose.yml` и `config.py`.

### Backend (Flask)

| Переменная | Описание | Значение по умолчанию (Docker) |
| --- | --- | --- |
| `DATABASE_URL` | Строка подключения к PG (обычно через PgBouncer) | `postgresql://botplus_user:botplus_password@pgbouncer:6432/botplus_db` |
| `MINIO_ENDPOINT` | Хост S3-хранилища | `minio:9000` |
| `MINIO_ACCESS_KEY` | Логин S3 | `minioadmin` |
| `MINIO_SECRET_KEY` | Пароль S3 | `minioadmin` |
| `MINIO_SECURE` | Использовать ли HTTPS для S3 | `False` |
| `JWT_SECRET` | Секрет для подписи токенов | `change-me` |
| `UPLOAD_FOLDER` | Временная папка для загрузок | `/app/server/uploads` |

### Frontend (Build time)

Проект настроен на автоматическое определение API.

* **Local Development**: Запросы проксируются через `src/setupProxy.js` на `:5000`.
* **Production**: Используются относительные пути (`/api/...`).

### TiTiler (GeoTIFF Server)

| Переменная | Зачем нужна |
| --- | --- |
| `AWS_S3_ENDPOINT` | Указывает GDAL ходить в наш локальный MinIO (`minio:9000`) |
| `AWS_HTTPS` | `FALSE` (отключает SSL handshake для внутреннего трафика) |
| `AWS_VIRTUAL_HOSTING` | `FALSE` (использует path-style access `host/bucket/file`) |

---

## 🐳 Запуск в Docker (Рекомендуемый)

Проект использует сложную оркестрацию из 5 сервисов. Ручной запуск через `docker run` не рекомендуется.

### Docker Compose

```bash
# 1. Сборка и запуск в фоновом режиме
docker compose up -d --build

# 2. Просмотр логов (чтобы убедиться, что БД инициализировалась)
docker compose logs -f app

```

**Сервисы в стеке:**

1. **`app`** (:5580) — Основное приложение (Flask + React Static).
2. **`db`** (:5432) — PostgreSQL 16 + PostGIS 3.4.
3. **`minio`** (:9000, :9001) — S3-хранилище файлов.
4. **`pgbouncer`** (:6432) — Пулер соединений для БД.
5. **`titiler`** (:8000) — Сервер рендеринга GeoTIFF (COG).

> **Healthcheck:** При первом запуске скрипт `init_pg_auth.py` может ждать готовности БД до 30 секунд.

---

## 🧑‍💻 Запуск в разработке (Гибридный режим)

Так как поднять PostGIS и MinIO локально "руками" сложно, рекомендуется гибридный подход: **Инфраструктура в Docker**, а **Код локально**.

### Шаг 1: Инфраструктура

Запустите только базы данных и вспомогательные сервисы:

```bash
docker compose up -d db minio pgbouncer titiler

```

*Убедитесь, что порты `5432`, `9000`, `9001`, `6432` свободны.*

### Шаг 2: Backend (Python)

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)

# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка ENV для локального запуска (переопределяем Docker-хосты на localhost)
export DATABASE_URL="postgresql://botplus_user:botplus_password@localhost:6432/botplus_db"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_SECURE="False"
export UPLOAD_FOLDER="./uploads"  # Создайте эту папку

# 3. Инициализация БД (если первый раз)
python init_pg_auth.py

# 4. Запуск
python app.py

```

*Сервер запустится на `http://127.0.0.1:5000`.*

### Шаг 3: Frontend (React)

```bash
# В корне проекта
npm install
npm start

```

*Фронтенд запустится на `http://localhost:3000`. Благодаря `setupProxy.js`, запросы `/api` будут улетать на ваш локальный Python-сервер.*

---

## 🚀 Продакшн (Deploy)

Контейнер `app` уже запускается через **Gunicorn** с поддержкой **Gevent** (см. `docker-compose.yml` -> `command`).
Вам нужно лишь настроить **Nginx** как реверс-прокси перед Docker-портом `5580`.

**Пример конфигурации Nginx (`/etc/nginx/sites-available/botplus`):**

```nginx
server {
    server_name maps.yourdomain.com;

    # Лимит на загрузку больших GeoTIFF/Панорам
    client_max_body_size 500M;

    location / {
        # Проксируем на порт Docker-контейнера (5580)
        proxy_pass [http://127.0.0.1:5580](http://127.0.0.1:5580);
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Для поддержки долгих запросов (загрузка файлов)
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}

```

---

## 🧭 API (Справочник)

Все эндпоинты имеют префикс `/api`.

### 🔐 Аутентификация (Custom JWT)

*Токены хранятся в HttpOnly Cookie.*

* `POST /api/auth/login` — Вход `{username, password}`.
* `GET /api/auth/me` — Проверка сессии. Возвращает `{authenticated: true, user: {...}}`.
* `POST /api/auth/logout` — Очистка куки.

### 📐 Векторные данные (PostGIS)

* `GET /api/vector/databases` — Список подключенных баз.
* `GET /api/vector/layers/{db_name}` — Список таблиц с геометрией.
* `GET /api/vector/tiles/combined/{db}/{z}/{x}/{y}.pbf` — **MVT Тайлы**. Динамическая генерация Mapbox Vector Tiles из PostGIS.
* `GET /api/vector/styles/{db}/{schema}/{table}` — Получение стилей слоя (Single/Categorized).

### 📷 Панорамы 360°

* `GET /api/panoramas` — Список панорам (поддерживает BBOX фильтрацию).
* `POST /api/upload` — Загрузка (Multipart). Извлекает EXIF, сохраняет в MinIO + PostGIS.

### 🦅 Ортофотопланы

* `GET /api/orthophotos` — Список загруженных карт.
* `POST /api/upload_ortho` — Загрузка GeoTIFF. Файл сохраняется в MinIO, границы вычисляются через GDAL.

---

## 🖥️ Фронтенд (Архитектура)

Структура `src/components/maps` полностью модульная:

* **State Management (Zustand)**:
* `useMapStore.ts` — Состояние растровых слоев (Орто).
* `useVectorStore.ts` — Кэш векторных данных и стилей.
* `useUIStore.ts` — Управление панелями (Layers, Pano, Vector).


* **Слои (`layers/`)**:
* `VectorLayerRenderer` — Умный рендеринг MVT через `leaflet.vectorgrid`.
* `OrthoLayer` — Формирует ссылки на TiTiler.
* `PanoLayer` — Кластеризация маркеров.


* **Core**:
* `CustomZoomControl` — Кастомные кнопки зума.
* `MapEvents` — Обработка кликов и контекстного меню.



---

## 🧯 Troubleshooting

### 1. Ошибка "MinIO Connection Refused"

Если TiTiler или Backend не видят MinIO:

* Проверьте, что все сервисы в одной сети (docker network).
* В `docker-compose.yml` проверьте переменные `MINIO_ENDPOINT` (должно быть `minio:9000`, а не localhost).

### 2. Не грузятся тайлы карты (404/500)

* **Vector**: Убедитесь, что в таблице PostGIS есть геометрия и SRID=4326. Проверьте логи `app` на ошибки SQL.
* **Ortho**: Откройте консоль браузера (Network). Если ошибка от TiTiler, проверьте логи контейнера `titiler`. Возможно, он не может скачать файл из MinIO из-за настроек региона/бакета.

### 3. "Index.html not found"

* Убедитесь, что Docker-образ собрался корректно. Frontend билдится на этапе `FROM node:22-alpine AS ui`. Проверьте наличие папки `/app/public/build` внутри контейнера.

---

## 🧪 Быстрые команды

```bash
# 🔥 Полный перезапуск (с пересборкой)
docker compose down
docker compose up -d --build

# 📜 Чтение логов бэкенда
docker compose logs -f app

# 🗑️ Очистка базы данных (Удаление томов!)
docker compose down -v

```

---

## 📜 Лицензия

© Botplus Maps. Enterprise GIS Solution.

```

```