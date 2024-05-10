import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Header from './Header'; // Убедитесь, что путь до компонента верный

const ProfilePage = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    sessionStorage.removeItem('auth'); // Удаляем флаг аутентификации из sessionStorage
    navigate('/login'); // Перенаправляем пользователя на страницу входа
  };

  return (
    <div className="background">
      <Header />
      <div className="profile-page">
        <h1 className="profile-title">Профиль пользователя</h1>
        <div className="profile-actions">
          <Link to="/upload">
            <button className="button">Загрузить</button>
          </Link>
          <button className="button" onClick={handleLogout}>Выйти</button>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
