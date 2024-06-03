const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  mode: 'development',
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
  },
  devServer: {
    host: '0.0.0.0',
    allowedHosts: 'all',
    port: 3000,
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
    historyApiFallback: true,
    proxy: {
      '/api': {
        target: 'http://backend:5000',
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: 'wss://botplus.ru',
        ws: true,
        secure: true,
        changeOrigin: true,
        pathRewrite: {'^/ws': ''},
      },
    },
    hot: false, // Отключить HMR
    liveReload: false, // Отключить live reload
    client: {
      overlay: {
        errors: true,
        warnings: false,
      },
      logging: 'info',
      webSocketURL: {
        hostname: 'localhost', // Изменено для отладки
        port: '3000',
        pathname: '/ws',
        protocol: 'ws',
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
      {
        test: /\.(png|jpe?g|gif|svg)$/i,
        type: 'asset/resource',
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html',
    }),
  ],
};
