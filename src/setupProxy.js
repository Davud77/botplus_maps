const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:5000', // Адрес вашего Python сервера
      changeOrigin: true,
      // Если ваш Flask не использует префикс /api, раскомментируйте строку ниже:
      // pathRewrite: { '^/api': '' },
    })
  );
};