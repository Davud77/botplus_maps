// src/components/LoginPage.tsx
import React, { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { login as loginApi } from '../utils/api';
import { useAuth } from '../hooks/useAuth';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    try {
      const data = await loginApi(username, password);
      if (data.status === 'success') {
        login();
        navigate('/');
      } else {
        setError(data.message || 'Неверное имя пользователя или пароль');
      }
    } catch (error: any) {
      setError('Ошибка при подключении к серверу: ' + error.message);
    }
  };

  return (
    <div className="login">
      <div className="login-screen">
        <div className="app-title">
          <h1>Авторизация</h1>
        </div>

        <form className="login-form" onSubmit={handleLogin}>
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

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="button buttonlogin btn-primary btn-large btn-block">Вход</button>
          <a className="login-link" href="https://t.me/localdisk_d">Забыли пароль?</a>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;