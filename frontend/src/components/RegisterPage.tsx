
import React, { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const RegisterPage: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const navigate = useNavigate();

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccessMessage('');

    try {
      const response = await axios.post('https://api.botplus.ru/register', {
        username,
        password,
      });
      if (response.data.status === 'success') {
        setSuccessMessage('Регистрация прошла успешно!');
        // Через 2 сек перенаправим на логин:
        setTimeout(() => {
          navigate('/login');
        }, 2000);
      } else {
        setError(response.data.message || 'Ошибка при регистрации');
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
          <h1>Регистрация</h1>
        </div>

        <form className="login-form" onSubmit={handleRegister}>
          <div className="control-group">
            <input
              type="text"
              className="login-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              id="login-name"
            />
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
          </div>

          {error && <div className="error-message">{error}</div>}
          {successMessage && <div className="success-message">{successMessage}</div>}

          <button type="submit" className="button buttonlogin btn-primary btn-large btn-block">
            Зарегистрироваться
          </button>
        </form>
      </div>
    </div>
  );
};

export default RegisterPage;