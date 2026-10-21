# ADR 0002: короткие изолированные транзакции PostgreSQL

Дата: 2026-10-21. Статус: реализовано в пакете M0.2.

## Проблема

Контроллеры создавались один раз и сохраняли один psycopg2 connection. Читающие методы оставляли транзакцию открытой; фоновые GDAL-задачи обращались к тому же manager/db. Commit или rollback одного запроса мог завершить чужую транзакцию. Длительные операции S3 удерживали доступ к БД, а transaction-mode PgBouncer не мог вернуть такой backend в пул.

Дополнительно vector API самостоятельно собирал DSN, поэтому мог обращаться к другой роли/хосту, чем auth и catalog. Сетевой monkey patch gevent сам по себе не обеспечивает совместную работу блокирующего libpq с event loop.

## Решение

`Database` — фабрика без сохранённого connection. Каждый `cursor()` открывает своё соединение и владеет его полным жизненным циклом. Фабрику можно передавать контроллерам, запросам и задачам; открытый connection между ними не передаётся.

```python
with db.cursor() as cursor:
    cursor.execute("SELECT id FROM assets WHERE id = %s", (asset_id,))
    row = cursor.fetchone()
# Read-only transaction rolled back; cursor and connection closed.

with db.cursor(write=True) as cursor:
    cursor.execute("UPDATE assets SET status = %s WHERE id = %s", (status, asset_id))
    cursor.execute("INSERT INTO events (asset_id) VALUES (%s)", (asset_id,))
# Both statements commit together only after successful exit.
```

Обычный read context выполняется в PostgreSQL `READ ONLY`, на выходе rollback/close. Write context делает commit только при нормальном выходе; при ошибке, отмене или неудаче commit выполняется rollback/close. Ошибка rollback не скрывает исходную ошибку и не отменяет попытку закрытия соединения.

Вложенные контексты независимы и **не являются savepoints**. Для атомарной операции над несколькими таблицами используется один context/cursor. Частичное обновление координат панорамы читает недостающую координату с `FOR UPDATE` и записывает геометрию в той же транзакции.

SQL-результаты нужно получить внутри блока. Не возвращать живой cursor/generator из него. Построение объектов каталога и сетевые вызовы S3/TiTiler/GDAL выполняются после закрытия транзакции. Массовые каталоги по-прежнему требуют отдельной пагинации/тайлинга; освобождение соединений само по себе не ограничивает объём `fetchall()`.

## Настройки и pooling

Все пути используют один `DATABASE_URL`. Для legacy vector API допускается заменить только имя базы, сохранив хост, порт, пользователя и SSL-настройки. Фабрика не печатает DSN и не сохраняет его в ответе API. Старые методы `get_cursor()/commit()/rollback()` с неявным общим connection удалены из внутренних вызовов.

| Переменная | По умолчанию | Область |
|---|---|---|
| `DB_CONNECT_TIMEOUT_SECONDS` | 5 секунд | Новое подключение libpq |
| `DB_STATEMENT_TIMEOUT_MS` | 30000 ms | Каждый SQL statement в обычной транзакции |
| `DB_IDLE_TRANSACTION_TIMEOUT_MS` | 10000 ms | Простой внутри обычной транзакции |

SQL-настройки задаются через `SET LOCAL`, поэтому действуют до commit/rollback и не остаются следующему клиенту transaction-mode PgBouncer. Не используются libpq startup `options`, которые многие конфигурации pooler отвергают. Timeout подключения не является общей гарантией времени DNS-resolution или всех сетевых операций; при нескольких DSN hosts libpq может применять его отдельно.

Создание PostgreSQL database — отдельный legacy административный путь с явным autocommit: PostgreSQL не разрешает `CREATE DATABASE` внутри транзакции. Transaction-local statement/idle timeout к этому пути не применяется. Создание обычного слоя PostGIS, включая таблицу, геометрию и индекс, теперь выполняется атомарно в одной транзакции. Административные маршруты требуют отдельной модели прав M1.

На текущем этапе отдельного Python connection pool нет: короткие клиентские connections работают через развёрнутый PgBouncer. Это исправляет владение транзакциями, но не заменяет лимиты числа клиентов и нагрузочные испытания. Поведение именно развёрнутой версии PgBouncer требует отдельной full-stack проверки.

## Gevent и запуск

Когда `gevent.monkey` уже пропатчил socket, перед первым подключением устанавливается psycogreen wait callback, если другой callback ещё не установлен. Обычные threaded/synchronous CLI/test процессы не monkey-patchятся. В отдельном тестовом процессе patch выполняется до импорта драйвера, как при Gunicorn gevent worker.

DB/S3 initialization убрана из импорта модулей контроллеров: blueprint factories создают зависимости при сборке приложения. Обязательный route import/initialization больше не скрывается широким `except` с продолжением работы без API. Bootstrap-скрипт БД пробрасывает ошибку, чтобы entrypoint завершился с ненулевым кодом.

Временный startup DDL ещё не заменён системой миграций. Его транзакции сериализуются `pg_advisory_xact_lock` по одному ключу приложения, чтобы Gunicorn workers не создавали одну таблицу/индекс одновременно. Это переходная мера, не миграционная история. При больших первичных индексах может понадобиться явно увеличенный SQL timeout для bootstrap; будущее release-job должно иметь отдельный лимит и не выполняться в web worker.

После изменения зависимостей нужно пересобрать backend image; копирования Python-файлов в старый контейнер без `psycogreen` недостаточно.

## Проверка

- Одновременные commit и rollback из двух потоков одной фабрики: сохраняется только правильная запись, backend PID различаются, connections закрыты.
- Read-only context отвергает запись; SQL-ошибка/отмена/ранний return/ошибка commit не оставляют connection открытым.
- Statement timeout отменяет `pg_sleep`; idle timeout закрывает простаивающий transaction; следующий запрос работает на новом connection.
- Gevent subprocess: два SQL-запроса перекрываются во времени, независимый ticker не блокируется, connections различаются и закрываются.
- HTTP-пути панорам проверяются с настоящим PostGIS; storage probe подтверждает освобождение DB до загрузки/удаления объекта.
- CRUD ортофото, частичное обновление панорамы, MVT/GeoJSON и атомарный отказ создания слоя проверяются на PostGIS.
- Изолированный тест параллельного startup DDL проверяет блокировку инициализации.

Локальные integration tests используют только явный `TEST_DATABASE_URL` отдельного временного PostgreSQL. CI поднимает собственный PostGIS 16; `REQUIRE_DATABASE_TESTS=1`, `TEST_POSTGIS=1` и `REQUIRE_GDAL_TESTS=1` не позволяют принять отсутствие тестовых зависимостей за успешную проверку.

## Что это не завершает

Durable jobs, transactional outbox для согласованности S3/DB, миграции schema versions, проектные права, readiness, пагинация, streaming downloads и benchmark на целевых объёмах остаются отдельными задачами дорожной карты. API health пока не заменяет полноценную проверку состояния зависимостей.

## Источники

- [Psycopg: транзакции, threading и green threads](https://www.psycopg.org/docs/usage.html#thread-and-process-safety).
- [Psycogreen: адаптация psycopg2 к gevent](https://github.com/psycopg/psycogreen).
- [PostgreSQL 16: SQL/idle transaction timeouts](https://www.postgresql.org/docs/16/runtime-config-client.html).
