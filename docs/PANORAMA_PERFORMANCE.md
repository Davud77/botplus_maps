# Panorama catalog and coverage at scale

The list uses a 200-item keyset page and transactional active/trash counters.
Default catalog requests do not count or transfer the whole table. Photo insert,
soft delete, restore, movement and purge update the counters and a five-level
spatial summary in the same PostgreSQL transaction. TRUNCATE resets the indexes.

Map requests return at most 1,000 canvas points/clusters. A materialized visible
subset prevents the ID ordering from scanning unrelated rows. Requests are
cancelled on navigation, stale responses are ignored and the padded visible area
is reused for small pans.

Below zoom 18, surveyed coverage is rendered as blue canvas lines. Segments join
consecutive imported photos within one source directory, with a maximum 25 m
separation and a 15-minute timestamp gap when timestamps are known. They describe
survey coverage, not road routing. Distant surveys and separate source folders
are not bridged. Above zoom 18, individual photo points are shown.

Coverage has precomputed simplified geometries at levels 0, 4, 8, 12 and 16 in
256-photo chunks. Triggers mark changed chunks; the media worker refreshes them
in batches, idle workers drain remaining changes, and viewport reads refresh
changed visible chunks. Opening a map does not merge every original segment.
Simplification is capped at 5 m deviation. A versioned upgrade removes old links longer than 25 m and rebuilds the existing display pyramid. The first upgrade builds these derived indexes once. Original media is unchanged.

Local Docker/PostGIS benchmark, 1,000,000 synthetic georeferenced rows:

| Request | Time | Response |
| --- | ---: | ---: |
| Catalog, 200 records with total | 116 ms | 43 KB |
| Distant map groups | 65 ms | 100 B |
| Dense close-up map, bounded groups | 113 ms | 606 B |
| Simplified survey coverage | 137 ms | 41 KB |

These are local synthetic query measurements, not NAS image download timings.
A production baseline with 51,845 active records returned 50,000 map points
(2.73 MB) in 873 ms before browser rendering. The new endpoint caps output and
uses the spatial summaries. Page layouts were checked with long names and WKT
at desktop and 390 px widths. The coordinate readout shows the current zoom.

### Настройки отображения покрытия

В настройках слоя сохраняются `panorama`: режим auto/points, уровень точек (18–22), детализация fast/balanced/precise, цвета и размеры линий, контрастной обводки и точек. По умолчанию линии с белой обводкой сменяются синими точками с Z18. Клик по линии плавно приближает до выбранного уровня точек. Агрегатные зелёные маркеры не рисуются. Геометрия покрытия сохраняется во время анимации и повторно используется внутри загруженной области.

`GET /api/media/markers?points=1` возвращает максимум 1000 отдельных точек без кластеров. `GET /api/media/coverage?lines=1&detail=balanced` позволяет получить линии независимо от масштаба; варианты детализации ограничивают упрощение 5/2/0,2 м. Исходные разрывы более 25 м сохраняются.

`POST /api/media/coverage/rebuild` (editor/admin) ставит перестроение производной пирамиды в общую FIFO-очередь. Результат строится во временной таблице и заменяется атомарно; исходные фото и связи не изменяются. Прогресс доступен в заданиях и настройках слоя. После завершения слой обновляется.

### Публикация панорам

Сохранённая карта с `show_panoramas=true` публикует слой панорам вместе с его порядком, прозрачностью и оформлением. Общий каталог панорам остаётся доступен только после входа. Публичный просмотр использует отдельные GET-адреса `/api/public/maps/<slug>/panoramas`, `/panoramas/coverage`, `/panoramas/<id>` и `/panoramas/<id>/image`. Каждый запрос проверяет действующую публикацию и наличие слоя в опубликованной версии; панорамы из корзины исключены. Публичные метаданные не содержат путей NAS, source_ref, directory и служебного имени файла. Отключение публикации отзывает её адреса. Изображения отдаются без сохранения в HTTP-кеше.
