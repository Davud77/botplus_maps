const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  mode: 'development', // Установите 'development' или 'production'
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/', // Добавлено для корректной работы URL
  },
  devServer: {
    host: '0.0.0.0',
    allowedHosts: 'all',  // это позволит принимать запросы с любых хостов
    port: 3000,
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
    historyApiFallback: true, // Добавлено для поддержки маршрутизации в React
    proxy: {
      '/api': {
        target: 'http://backend:5000',
        changeOrigin: true,
        ws: true, // Прокси для WebSocket
      },
      '/ws': {
        target: 'wss://botplus.ru',
        ws: true,
        secure: true,
        changeOrigin: true,
        pathRewrite: {'^/ws': ''}, // Добавлено для устранения множественных /ws
      },
    },
    hot: true,
    liveReload: true,
    client: {
      overlay: {
        errors: true,
        warnings: false,
      },
      logging: 'info',
      webSocketURL: {
        hostname: 'botplus.ru',
        pathname: '/ws',
        port: '443', // Изменено на строку '443' для HTTPS
        protocol: 'wss',
      },
    },
    setupMiddlewares: (middlewares, devServer) => {
      devServer.app.use((req, res, next) => {
        try {
          decodeURIComponent(req.url);
        } catch (e) {
          console.error('Malformed URL:', req.url);
          res.status(400).send('Malformed URL');
          return;
        }
        next();
      });
      return middlewares;
    },
  },
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html',
    }),
  ],
};
