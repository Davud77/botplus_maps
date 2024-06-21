import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login as loginApi } from '../utils/api';
import useAuth from '../hooks/useAuth';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (event) => {
    event.preventDefault();
    setError(''); // Сброс ошибки перед новой попыткой входа

    try {
      const data = await loginApi(username, password);
      if (data.status === 'success') {
        login();
        navigate('/');
      } else {
        setError(data.message || 'Неверное имя пользователя или пароль');
      }
    } catch (error) {
      setError('Ошибка при подключении к серверу: ' + error.message);
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

          {error && <div className="error-message">{error}</div>} {/* Показываем сообщение об ошибке */}

          <button className="button buttonlogin btn-primary btn-large btn-block" onClick={handleLogin}>Вход</button>
          <a className="login-link" href="https://t.me/localdisk_d">Забыли пароль?</a>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
