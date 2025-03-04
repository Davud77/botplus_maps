import React, { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import axios from 'axios';

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
      const response = await axios.post('https://api.botplus.ru/login', {
        username,
        password,
      });
      if (response.data.status === 'success') {
        login();
        navigate('/');
      } else {
        setError(response.data.message || 'Неверное имя пользователя или пароль');
      }
    } catch (error: any) {
      console.error('Ошибка подключения:', error);
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
              placeholder="Имя пользователя"
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
              placeholder="Пароль"
              id="login-pass"
            />
            <label className="login-field-icon fui-lock" htmlFor="login-pass"></label>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="buttonlogin btn-primary btn-large btn-block">
            Войти
          </button>
          <a className="login-link" href="https://t.me/localdisk_d">
            Забыли пароль?
          </a>
          <p className="register-prompt">
            Нет аккаунта?{' '}
            <Link to="/register" className="register-link">
              Регистрация
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;