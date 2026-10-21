# Локальные инструменты и будущий импорт

Первая реализованная команда — **проверка GeoTIFF перед импортом**. Она работает локально, не запускает Flask/DB/MinIO, не загружает файл через browser, не преобразует оригинал и не публикует его на карте. Возобновляемая загрузка и no-copy registration будут добавлены в M2.

## Запуск в контейнере

Docker с работающим daemon; первый build получает базовый образ и пакеты из Интернета. После сборки проверку можно выполнять без сети. Файлы на NAS сначала доступны на хосте, затем монтируются в контейнер.

```sh
docker build -f Dockerfile.tools -t botplus-tools:local .
docker run --rm --network none \
  --mount type=bind,src=/srv/geodata,dst=/sources,readonly \
  botplus-tools:local inspect-raster /sources/ortho.tif > ortho-inspection.json
```

Замените `/srv/geodata` на существующую папку с данными. UID контейнера — 10001; администратор должен дать ему право чтения файла/прохода по папкам. Контейнер не должен получать root или writable-доступ ко всему диску ради чтения.

## Запуск в Python

Нужны GDAL и соответствующие ему Python bindings. Запускается из корня репозитория:

```sh
python -m server.cli inspect-raster /srv/geodata/ortho.tif > ortho-inspection.json
python -m server.cli inspect-raster /srv/geodata/ortho.tif --source-crs EPSG:32638
python -m server.cli inspect-raster /srv/geodata/ortho.tif --crs-file /srv/crs/local.prj
```

`--source-crs` / `--crs-file` описывает **исходные** координаты; это не команда перепроецирования. Существующий CRS override нужно задавать только если встроенное определение известно как отсутствующее/ошибочное. Оригинал не меняется; override фиксируется в отчёте. При отсутствии CRS команда не угадывает её по числам.

Поддержка локальной CRS означает возможность разобрать определение и найти корректную локально доступную операцию в WGS84. Она не означает, что достаточно произвольного названия МСК: может понадобиться datum, зона, параметры или grid. Сетевое скачивание PROJ grids выключено; приблизительная ballpark-операция запрещена.

## Результат

JSON содержит размер файла, размеры raster, полный WKT2, native bounds, уплотнённый WGS84 footprint/bbox, тип и block size каналов, список overviews и metadata hint COG. Для rotation используются все четыре affine-угла. GCP/RPC-only GeoTIFF и пересечение antimeridian пока отклоняются с явной ошибкой — им нужна отдельная подготовка.

Проверка читает заголовки, геопривязку и metadata, **не запускает** statistics/histogram/checksum или чтение всех пикселей. OS/GDAL могут читать вспомогательные metadata и служебные TIFF-структуры; время не является гарантированно константным для любого TIFF. На сотнях GB нет обязательного буфера такого же размера в RAM.

`validation=metadata_only` и `publication_ready=false`: это не полная structural COG validation и не проверка каждого блока. `mtime_ns/size_bytes` — fingerprint для обнаружения изменений, не криптографическая checksum. Источник не должен меняться во время проверки; read-only mount не запрещает запись в файл со стороны других программ на хосте.

При успехе exit code 0 и JSON в stdout. При ошибке exit code 2, объяснение в stderr. Отчёт содержит локальный путь — не выкладывайте его публично, если структура ваших каталогов закрыта.

## Следующие команды (ещё не реализованы)

Планируемый API CLI: подключение server source, batch import по manifest, upload/resume, статус/отмена jobs, проверка storage и управление CRS. Точные названия подкоманд закрепим вместе с job API. Не используйте пока старую веб-форму как доказанно надёжный способ загрузки TIFF на сотни GB.
