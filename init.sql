-- Создание таблицы пользователей
CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Вставка пользователя по умолчанию
INSERT INTO public.users (username, password) VALUES ('Гость', 'Гость');

-- Создайте другие таблицы, если необходимо