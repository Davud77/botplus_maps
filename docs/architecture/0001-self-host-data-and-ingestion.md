# ADR 0001: локальное хранение, версии и единый импорт

Дата: 2026-10-21. Статус: принято как направление; реализация по ROADMAP M1–M4.

## Контекст

Архивы находятся на собственных дисках. Копирование готового COG размером сотни GB в другое хранилище только ради отображения не должно быть обязательным. Веб и скрипты должны создавать одинаковые каталожные сущности. Браузер не выполняет GDAL-преобразование и не читает большие оригиналы в RAM. CRS источника может не иметь EPSG-кода.

## Решение

**Source adapter:** `filesystem(root_id, relative_key)` и `s3(endpoint_id, bucket, key, version_id)`. Absolute host paths/credentials не публикуются viewer. API разрешает root/key по каталогу; filesystem adapter проверяет канонический путь и symlinks внутри read-only root. Даже администраторский web endpoint не является произвольным file browser ОС. Изменение исходника после подключения приводит к invalid/stale, а не незаметному изменению опубликованной версии; нужны stat fingerprint, checksum и при необходимости filesystem snapshots/immutable permissions.

**Asset:** original/COG/preview/tile pyramid/manifest/grid. Оригинал и производная имеют разные lifecycle и права удаления. Подключённый read-only original не удаляется вместе с dataset. Storage root можно переместить изменением настройки адаптера без переписывания всех URL карты.

**Dataset version:** ссылки на source assets, validated CRS, operation definition, processing recipe/version и derived manifest. Только published version используется viewer. Переключение указателя версии происходит атомарно в DB; filesystem/S3 и DB не считаются одной транзакцией. Outbox, reconciliation и garbage collection устраняют незавершённые состояния.

**Job:** durable status/attempt/lease/idempotency key. Веб/CLI — разные клиенты одного job API. Если файл уже доступен серверу, ни браузер, ни CLI не передают его по сети. Для удалённой станции — resumable multipart с ограничением памяти/числа частей, сохранёнными upload IDs и проверкой целостности. Решение о публикации принимает сервер после проверки, а не клиент после последнего chunk.

**CRS:** исходное определение WKT2/PROJJSON, назначенный override и operation pipeline — отдельные поля. Обозначение «МСК-05» без зоны, datum и подтверждённой операции недостаточно. Local grid resources версионируются и входят в backup/offline bundle. Политика production не разрешает молча выбирать ballpark transformation; при нехватке информации набор остаётся unpublished. Native rendering CRS и CRS цифровых измерений отделены от web display CRS.

**Display:** от API не требуется проксировать все байты оригиналов. Tile gateway обслуживает авторизованные IDs и manifests; renderer читает bounded windows/Range. Коллекции снимков ограничивают число кандидатов на один tile; low-zoom обзоры могут быть заранее подготовлены. Source access и shared cache соблюдают project ACL.

## Последствия

- Односерверная установка возможна на обычном диске; S3 и облачная инфраструктура не обязательны.
- Готовый COG подключается без производного полного экземпляра, но кэши/каталог всё равно занимают место.
- Неоптимизированный raster требует производной и scratch; точный budget устанавливается recipe/preflight и проверяется перед стартом.
- NAS не делает чтение бесплатным: latency/IOPS/read amplification входят в тесты.
- Нет одновременной реализации двух разных import pipelines для CLI и web.
- Пока это ADR, не обещание, что legacy MinIO-only app уже умеет no-copy. Первый проход реализации теперь включает HTTP CLI, no-copy локального COG, подготовку GeoTIFF отдельным worker и PostgreSQL jobs. Полные dataset versions, outbox/reconciliation и GC пока не реализованы.

## Отвергнутые варианты

- Обязательное помещение всех исходников в публичный bucket — лишнее копирование и нарушение модели private data.
- GeoJSON всего слоя/оригинал raster в browser — память и задержки растут вместе с архивом.
- Обработка внутри HTTP worker — нет надёжного restart/retry и изоляции ресурсов.
- Принудительная перезапись всех original CRS в 3857 — потеря исходной семантики и лишние затраты.

## Проверка реализации

Два клиента импортируют одинаковый source с одним idempotency key — опубликован один результат. Worker перезапускается на каждой стадии — оригинал цел, job восстанавливается. Симлинк за пределы root отклоняется. Без доступа к проекту нельзя получить ни tile, ни manifest, ни URL оригинала, включая cache hit. CLI и web выдают эквивалентные manifests. Готовый COG 100+ GB не копируется при no-copy import; RSS не растёт пропорционально файлу. Некорректная/неполная CRS не публикуется автоматически.
