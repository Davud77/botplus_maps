import React, { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [pending, setPending] = useState<boolean>(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setPending(true);

    try {
      // Новый контракт: login(username, password) -> Promise<boolean>
      const ok = await login(username, password);
      if (ok) {
        navigate('/');
      } else {
        setError('Неверное имя пользователя или пароль');
      }
    } catch (e: any) {
      console.error('Ошибка подключения:', e);
      setError('Ошибка при подключении к серверу: ' + (e?.message || 'неизвестная ошибка'));
    } finally {
      setPending(false);
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
              name="username"
              autoComplete="username"
              required
              disabled={pending}
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
              name="password"
              autoComplete="current-password"
              required
              disabled={pending}
            />
            <label className="login-field-icon fui-lock" htmlFor="login-pass"></label>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="buttonlogin btn-primary btn-large btn-block" disabled={pending}>
            {pending ? 'Входим…' : 'Войти'}
          </button>
          <a className="login-link" href="https://t.me/localdisk_d" target="_blank" rel="noreferrer">
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
