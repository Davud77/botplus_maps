import React from 'react';
import { Link } from 'react-router-dom';

const Header = () => {
  return (
    <div className="navigation-menu">
        <div className="logo-menu">
        <Link to="/" className="logo">
        <img src="/images/logo.png" alt="Логотип" style={{ height: '50px' }} />
      </Link>
      <Link to="/map">
        <button className="button button_nav">Карты</button>
      </Link>
        </div>
      
      <div className="profile_nav">
        <Link to="/profile" className="profile-link">
          <img src="/images/profile-icon.png" alt="Профиль" style={{ height: '50px' }} />
          
        </Link>
      </div>
    </div>
  );
};

export default Header;
