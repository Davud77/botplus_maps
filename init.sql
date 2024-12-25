-- Создание таблицы пользователей
CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Вставка пользователя по умолчанию
INSERT INTO public.users (username, password) VALUES ('Гость', 'Гость');

-- Создание таблицы панорам
CREATE TABLE public.panolist (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    tags VARCHAR(255),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES public.users(id),
    file_size DOUBLE PRECISION,
    file_type VARCHAR(50),
    full_pano_width_pixels INTEGER,
    full_pano_height_pixels INTEGER,
    first_photo_date TIMESTAMP,
    model VARCHAR(255),
    altitude DOUBLE PRECISION,
    fov DOUBLE PRECISION,
    focal_length DOUBLE PRECISION,
    geom GEOMETRY(PointZ, 4326)
);

-- Вставка тестовых данных в таблицу panolist (опционально)
INSERT INTO public.panolist (
    filename,
    latitude,
    longitude,
    tags,
    upload_date,
    user_id,
    file_size,
    file_type,
    full_pano_width_pixels,
    full_pano_height_pixels,
    first_photo_date,
    model,
    altitude,
    fov,
    focal_length,
    geom
) VALUES (
    'example.jpg',
    55.7558,
    37.6173,
    'пример,тест',
    CURRENT_TIMESTAMP,
    1,
    2.5,
    'image/jpeg',
    4000,
    2000,
    '2023-11-17 12:00:00',
    'Canon EOS 5D Mark IV',
    200.0,
    90.0,
    50.0,
    ST_GeomFromText('POINT Z(37.6173 55.7558 200.0)', 4326)
);

-- Создайте другие таблицы, если необходимо
