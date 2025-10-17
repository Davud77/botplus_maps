```markdown
# Botplus Maps (Panorama Viewer)

Полная документация проекта: назначение, архитектура, схема БД, запуск в DEV/PROD, Docker/Compose, переменные окружения, API, троблшутинг.

---

## 🔎 Что это такое

**Botplus Maps** — веб-приложение для работы с интерактивной картой, панорамами 360° и ортофотопланами (COG/GeoTIFF).  
Фронтенд — **React + TypeScript (CRA)**.  
Бэкенд — **Flask (Python 3.11)** со слоистой архитектурой (**routers/controllers → services → repositories → storage/database**).  
Хранилища по умолчанию:
- **SQLite** (файл `./data/botplus.db`, без отдельного контейнера)
- Файлы загрузок на локальном диске (`server/uploads/...`)

Ключевые возможности:
- 🔑 Авторизация (cookie-сессия)
- 🗺️ Базовые слои карт (OSM, Google, ESRI и т.д.)
- 🖼️ Просмотр панорам 360° (Marzipano)
- 📤 Загрузка/удаление/массовые операции над панорамами
- 🗂️ Загрузка ортофото, хранение границ (bounds)
- ✏️ Редактирование метаданных (теги и пр.)
- 🧭 Поиск/переход по координатам
- 🐳 Готовность к деплою через Docker/Compose
- 🧪 Healthcheck для оркестрации

Публичный API (при продовом деплое): `https://api.botplus.ru` (пример, укажите свой домен/хост).

---

## 📦 Структура репозитория

```

.
├── data/
│   └── botplus.db                # SQLite (создается init_db.py)
├── public/
│   ├── icons/                    # PWA-иконки
│   ├── images/
│   │   ├── svg/                  # SVG-иконки (слои, панорамы, и т.п.)
│   │   ├── GoogleMaps.png
│   │   ├── GoogleSatellite.png
│   │   ├── OSM.png
│   │   └── ...
│   ├── videos/
│   │   └── banner.mp4
│   ├── favicon.ico
│   ├── index.html
│   └── manifest.json
├── server/
│   ├── alembic/                  # (опционально) миграции, если используются
│   ├── app/                      # (если есть) внутренние модули
│   ├── controllers/              # Flask Blueprints: auth, pano, ortho
│   ├── managers/                 # (если есть) фасады/оркестраторы
│   ├── models/                   # (если есть) ORM/датаклассы
│   ├── uploads/                  # файлы панорам/ортофото/тайлы
│   ├── app.py                    # точка входа Flask (create_app/WSGI)
│   ├── config.py                 # конфигурация (CORS/cookie/пути/лимиты)
│   ├── database.py               # доступ к БД (SQLite по умолчанию)
│   ├── init_db.py                # инициализация схемы и дефолтного пользователя
│   ├── requirements.txt          # зависимости бэкенда
│   └── storage.py                # локальное файловое хранилище
├── src/
│   ├── assets/css/               # стили страниц/компонентов
│   ├── components/
│   │   ├── maps/
│   │   │   ├── baseLayer/BaseLayer.tsx
│   │   │   ├── orthoLayer/{CogLayer,MapWithOrtho,OrthoLayer,OrthoPanel}.tsx
│   │   │   └── panoLayer/{PanoLayer,PanoLayerButton,PanoramaViewer,PointInfo,
│   │   │                    SelectionPanel}.tsx
│   │   ├── ContextMenu.tsx
│   │   ├── CustomZoomControl.tsx
│   │   ├── MapContainerCanvas.tsx
│   │   ├── MapPage.tsx
│   │   ├── Search.tsx
│   │   ├── Header.tsx
│   │   ├── Home.tsx
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── ProfilePage.tsx
│   │   ├── ProfileNav.tsx
│   │   ├── UploadPano.tsx
│   │   └── UploadOrtho.tsx
│   ├── contexts/AuthContext.tsx
│   ├── hooks/useAuth.ts
│   ├── types/*.d.ts              # типы для внешних либ (marzipano, proj4 и т.п.)
│   ├── utils/api.ts              # обёртки вызовов API
│   ├── App.tsx
│   ├── index.css
│   ├── index.tsx
│   └── routes.tsx
├── Dockerfile
├── docker-compose.yml
├── package.json
├── package-lock.json
├── tsconfig.json
└── README.md

````

> Важно: вся прикладная логика — на сервере (валидация, правила, права). На фронте — только отображение и вызовы API.

---

## 🧰 Схема базы данных

### Таблицы

```sql
-- Пользователи
CREATE TABLE IF NOT EXISTS users (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  username  TEXT UNIQUE NOT NULL,
  password  TEXT NOT NULL                    -- пароль в виде хеша
);

-- Панорамы
CREATE TABLE IF NOT EXISTS panolist (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  filename                 TEXT NOT NULL,    -- относительный путь/имя файла
  latitude                 REAL,             -- широта
  longitude                REAL,             -- долгота
  user_id                  INTEGER,          -- FK -> users.id (кто загрузил)
  file_type                TEXT,             -- mime/расширение
  file_size                INTEGER,          -- байты
  full_pano_width_pixels   INTEGER,
  full_pano_height_pixels  INTEGER,
  first_photo_date         TEXT,             -- ISO8601
  model                    TEXT,             -- камера/модель
  altitude                 REAL,
  focal_length             REAL,
  tags                     TEXT,             -- CSV/JSON строка тегов
  upload_date              TEXT,             -- ISO8601
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Ортофотопланы
CREATE TABLE IF NOT EXISTS ortholist (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,    -- относительный путь/имя файла/каталога тайлов
  bounds   TEXT NOT NULL     -- JSON: [minX,minY,maxX,maxY] или GeoJSON
);
````

> Файл БД: `./data/botplus.db`. Создаётся автоматически `server/init_db.py`.
> Дефолтный пользователь (для DEV): `user / password` (обязательно поменяйте в проде).

---

## ⚙️ Переменные окружения

### Backend

| Переменная              | Назначение                               | Значение по умолчанию   |
| ----------------------- | ---------------------------------------- | ----------------------- |
| `SECRET_KEY`            | Секрет Flask для cookie-сессий           | `change-me`             |
| `CLIENT_ORIGINS`        | Разрешённые CORS Origins (через запятую) | `http://localhost:3000` |
| `SESSION_COOKIE_DOMAIN` | Домен cookie (например `.botplus.ru`)    | пусто                   |
| `COOKIE_SECURE`         | `1` — только HTTPS                       | `0`                     |
| `COOKIE_SAMESITE`       | `Lax` / `None` / `Strict`                | `Lax`                   |
| `DB_FILE`               | Путь к SQLite                            | `/app/data/botplus.db`  |
| `UPLOAD_FOLDER`         | Корень загрузок                          | `/app/server/uploads`   |
| `MAX_CONTENT_LENGTH`    | Макс. размер запроса (байты)             | `104857600` (пример)    |

### Frontend (`.env` в корне)

```
REACT_APP_API_URL=http://localhost:5000
REACT_APP_MAP_TILE_LAYER=https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
```

> В проде укажите публичный URL API (например, `https://api.botplus.ru`).

---

## 🧑‍💻 Запуск в разработке (без Docker)

### 1) Backend

```bash
# 1. Установить Python 3.11 (macOS обычно уже ок), затем:
python3 -m venv .venv
source .venv/bin/activate

# 2. Зависимости
pip install -r server/requirements.txt

# 3. Инициализация БД и дефолтного пользователя
python server/init_db.py

# 4. Запуск сервера (http://localhost:5000)
python server/app.py
```

### 2) Frontend

```bash
npm install
npm start   # http://localhost:3000
```

> `REACT_APP_API_URL` должен указывать на бек (`http://localhost:5000`).
> Авторизационные запросы используют cookie, не забывайте включить `credentials` на фронте.

---

## 🐳 Запуск в Docker

### Docker Compose (рекомендуется)

```bash
docker compose build
docker compose up -d
# Откройте: http://localhost:5580
# Healthcheck: GET http://localhost:5580/api/health
```

**Что делает compose:**

* Собирает фронтенд (CRA) → копирует сборку в образ Flask
* Запускает единый контейнер приложения (API + статика)
* Монтирует тома:

  * `./data -> /app/data` (SQLite)
  * `./server/uploads -> /app/server/uploads` (файлы)
* Пробрасывает `5580:5000`
* Экспортирует переменные окружения (см. `docker-compose.yml`)

### Чистый Docker

```bash
docker build -t botplus .
docker run --name botplus \
  -p 5580:5000 \
  -e SECRET_KEY="prod-change-me" \
  -e CLIENT_ORIGINS="https://your-frontend.example" \
  -e COOKIE_SECURE=1 -e COOKIE_SAMESITE=None \
  -v $PWD/data:/app/data \
  -v $PWD/server/uploads:/app/server/uploads \
  -d botplus
```

---

## 🚀 Продакшн

Рекомендуется запуск через **Gunicorn** за **Nginx** (TLS/HTTP2/статик-кэш).

```bash
# внутри venv контейнера/сервера
pip install gunicorn
gunicorn --workers 3 --bind 0.0.0.0:5000 'server.app:create_app()'
```

Фрагмент Nginx:

```nginx
server {
  listen 80;
  server_name api.botplus.ru;

  # редирект на https если есть сертификаты
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name api.botplus.ru;

  ssl_certificate     /etc/letsencrypt/live/api.botplus.ru/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.botplus.ru/privkey.pem;

  client_max_body_size 200m;

  location / {
    proxy_pass         http://127.0.0.1:5000;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
  }
}
```

**Cookie в проде:**
`SESSION_COOKIE_DOMAIN=.botplus.ru`, `COOKIE_SECURE=1`, `COOKIE_SAMESITE=None`.

---

## 🧭 API (краткий справочник)

> Базовый путь: `/` (для фронтенд-статик) и `/api/*` (если включено префиксирование). Ниже — типовые эндпоинты; имена могут отличаться в вашей сборке (см. `server/controllers/*`).

### Health

* `GET /api/health` → `{"status":"ok"}`

### Auth

* `POST /login` → `{ status: "ok" }` (устанавливает cookie)

  * body: `{ "username": "user", "password": "password" }`
* `POST /logout` → `{ status: "ok" }`
* (опционально) `POST /register` → `{ status: "ok" }` (отключайте в проде)

### Панорамы

* `GET /panoramas` → список записей `panolist`
* `POST /upload` (multipart/form-data)

  * поля: `file` (image/*), доп. метаданные по необходимости
  * ответ: `{ id, filename, ... }`
* `PUT /pano_info/{id}` → обновление метаданных (например, `tags`)
* `DELETE /pano_info/{id}` → удаление файла и записи

### Ортофото

* `GET /orthophotos` → список `ortholist`
* `POST /upload_ortho` (multipart/form-data) → загрузка GeoTIFF/COG
* `DELETE /orthophotos/{id}`

### Примеры (curl)

```bash
# Логин
curl -i -c cookies.txt -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"password"}'

# Список панорам
curl -b cookies.txt http://localhost:5000/panoramas

# Загрузка панорамы
curl -b cookies.txt -F file=@/path/to/pano.jpg http://localhost:5000/upload

# Обновление тегов
curl -b cookies.txt -X PUT http://localhost:5000/pano_info/1 \
  -H "Content-Type: application/json" \
  -d '{"tags":"tag1,tag2"}'

# Удаление панорамы
curl -b cookies.txt -X DELETE http://localhost:5000/pano_info/1
```

---

## 🖥️ Фронтенд

* Точка входа: `src/index.tsx`, приложение: `src/App.tsx`, роуты: `src/routes.tsx`
* Авторизация: `src/contexts/AuthContext.tsx`, `src/hooks/useAuth.ts`
* Вызовы API: `src/utils/api.ts`
* Карта/панорамы/орто — в `src/components/maps/*`
* Стили: централизуйте новые стили в `src/index.css` (рекомендуется поддерживать единую палитру переменными CSS)

---

## 🔐 Безопасность и права

* Вся валидация/права — на сервере (контроллеры/сервисы).
* Для cookie-сессий включайте:

  * CORS с `credentials`
  * В проде: `COOKIE_SECURE=1`, `COOKIE_SAMESITE=None`, `SESSION_COOKIE_DOMAIN=.ваш.домен`
* Ограничивайте размер загрузок (`MAX_CONTENT_LENGTH`) и список допустимых MIME.

---

## 🔄 Миграции

Проект из коробки использует SQLite + инициализацию через `init_db.py`.
Если используете **Alembic**:

```bash
alembic upgrade head
```

или переносите схему в PostgreSQL/MySQL (потребуется адаптация `database.py` и/или слоя `repositories`).

---

## 🧯 Troubleshooting

* **500/CORS/Auth не работает** — проверьте `CLIENT_ORIGINS`, `SESSION_COOKIE_DOMAIN`, `COOKIE_SAMESITE`, `COOKIE_SECURE`, наличие `withCredentials` на фронте.
* **Фронт не видит API** — проверьте `REACT_APP_API_URL` и прокси-правила, порт доступности (:5000 локально / :5580 при Compose).
* **Файлы не грузятся** — проверьте права на `server/uploads/`, лимит `MAX_CONTENT_LENGTH`, MIME-фильтры.
* **Статика не отдается** — убедитесь, что CRA собран и сборка скопирована в образ (Dockerfile multi-stage).
* **БД отсутствует** — выполните `python server/init_db.py` и проверьте монтирование `./data`.

---

## 🧪 Быстрые команды

```bash
# DEV: backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
python server/init_db.py
python server/app.py  # :5000

# DEV: frontend
npm install
npm start            # :3000

# DOCKER
docker compose up -d --build
docker compose logs -f

# PROD (WSGI)
gunicorn --workers 3 --bind 0.0.0.0:5000 'server.app:create_app()'
```

---

## 📜 Лицензия

© Botplus. Все права защищены. Использование в вашей инфраструктуре согласно внутренним правилам.

---

## 📝 Приложение: что изменено по сравнению с «как было»

* Объединённый README с полной инструкцией (DEV/PROD/Docker).
* Уточнены **структура репозитория** и **схема БД** (users, panolist, ortholist).
* Добавлен раздел **переменных окружения** (CORS/cookie/пути/лимиты).
* Чёткий перечень **API** и примеры `curl`.
* Рекомендации по **безопасности** и **троблшутингу**.
* По умолчанию — **SQLite** без отдельного контейнера БД (проще стартовать).

```
```
USER, PASS = "newadmin", "New#Pass123"