# Используем официальный образ Node.js
FROM node:18

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы package.json и package-lock.json
COPY package.json package-lock.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем остальные файлы проекта
COPY . .

# Указываем порт, на котором будет запущен сервер
EXPOSE 3000

# Запускаем команду для старта приложения
CMD ["npm", "start"]
