import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Header from './Header';
import useAuth from '../hooks/useAuth';

const ProfilePage = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="background">
      <Header />
      <div className="profile-page">
        <h1 className="profile-title">Профиль пользователя</h1>
        <div className="profile-actions">
          <Link to="/upload">
            <button className="button">Загрузить панорамы</button>
          </Link>
          <Link to="/uploadortho">
            <button className="button">Загрузить ортофотопланы</button>
          </Link>
          <button className="button" onClick={handleLogout}>Выйти</button>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
