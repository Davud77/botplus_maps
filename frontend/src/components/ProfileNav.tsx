import React from 'react';
import { Link } from 'react-router-dom';

const ProfileNav = () => {
  return (
    <div className="profile_nav">
      <div className="profile-link">
        <img 
          src="/images/svg/profile-icon.svg" 
          alt="Profile"
          width="30"
          height="30"

        />
      </div>
      <div className="profile-dropdown">
        <Link to="/profile" className="profile-button">
          Профиль
        </Link>
        <button className="logout-button" onClick={() => handleLogout()}>
          Выйти
        </button>
      </div>
    </div>
  );
};

const handleLogout = () => {
  // Логика выхода из системы
  console.log('User logged out');
};

export default ProfileNav;