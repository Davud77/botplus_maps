# Используем официальный образ Node.js
FROM node:18

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Копируем все файлы в контейнер
COPY . .

# Открываем порт
EXPOSE 3000

# Указываем команду запуска
CMD ["sh", "-c", "npm install && npm start"]