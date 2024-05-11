import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (event) => {
    event.preventDefault();

    try {
      const response = await fetch('http://localhost:5000/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });

      const data = await response.json();
      if (response.ok) {
        // Асинхронное сохранение состояния аутентификации
        await new Promise((resolve) => {
          sessionStorage.setItem('auth', true);
          resolve();
        });
        navigate('/'); // Перенаправление на главную страницу после успешного сохранения
      } else {
        alert(data.message || 'Неверное имя пользователя или пароль');
      }
    } catch (error) {
      alert('Ошибка при подключении к серверу: ' + error.message);
    }
  };

  return (
    <div className="login">
      <div className="login-screen">
        <div className="app-title">
          <h1>Авторизация</h1>
        </div>

        <div className="login-form">
          <div className="control-group">
            <input
              type="text"
              className="login-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              id="login-name"
            />
            <label className="login-field-icon fui-user" htmlFor="login-name"></label>
          </div>

          <div className="control-group">
            <input
              type="password"
              className="login-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              id="login-pass"
            />
            <label className="login-field-icon fui-lock" htmlFor="login-pass"></label>
          </div>

          <button className="button buttonlogin btn-primary btn-large btn-block" onClick={handleLogin}>Вход</button>
          <a className="login-link" href="#">Забыли пароль?</a>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
