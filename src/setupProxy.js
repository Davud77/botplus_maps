const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'https://api.botplus.ru', // Целевой сервер (продакшн API)
      changeOrigin: true,
      secure: false, // Игнорировать ошибки SSL, если они возникнут
      pathRewrite: {
        '^/api': '', // Убираем префикс /api, чтобы сервер получил запрос /panoramas
      },
      onProxyRes: function (proxyRes, req, res) {
        // Логируем заголовки для отладки, если нужно
        // console.log('Proxy Headers:', proxyRes.headers);
      },
      onError: function (err, req, res) {
        console.error('Proxy Error:', err);
      }
    })
  );
};