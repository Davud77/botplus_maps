// src/setupProxy.js
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      // [FIX] Направляем запросы на локальный Python-сервер (Flask)
      target: 'http://127.0.0.1:5000', 
      
      changeOrigin: true,
      secure: false, // Игнорировать ошибки самоподписанных сертификатов (если есть)
      
      // [FIX] pathRewrite УДАЛЕН. 
      // Flask теперь настроен с url_prefix="/api", поэтому он ожидает полный путь /api/orthophotos.
      // Если мы срежем /api, Flask не найдет маршрут.

      onProxyRes: function (proxyRes, req, res) {
        // Можно раскомментировать для отладки, чтобы видеть заголовки от Python
        // console.log('Proxy received headers:', proxyRes.headers);
      },
      onError: function (err, req, res) {
        console.error('Proxy Error (не удалось соединиться с Python :5000):', err);
        res.writeHead(500, {
          'Content-Type': 'text/plain',
        });
        res.end('Something went wrong with the proxy. Is the Python server running on port 5000?');
      }
    })
  );
};