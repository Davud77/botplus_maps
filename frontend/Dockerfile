# Используем официальный образ Node.js
FROM node:18

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Устанавливаем дополнительные зависимости для разработки
RUN npm install -D webpack-cli @babel/preset-react

# Копируем все файлы в контейнер
COPY . .

# Проверяем содержимое папки public
RUN ls -l /app/public

# Открываем порт
EXPOSE 3000

# Указываем команду запуска
CMD ["npm", "start"]
