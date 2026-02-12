// src/components/Header.tsx
import React from 'react';
import { Link } from 'react-router-dom';

const Header: React.FC = () => {
  return (
    <div className="navigation-menu">
      <div className="first-box header-box">
        <Link to="/" className="logo">
          {/* В качестве fallback-текста можно оставить название или убрать совсем */}
          <img src="/images/logowhite2.png" alt="Логотип" />
        </Link>
        <Link to="/map">
          <button className="button button_nav">Карты</button>
        </Link>
      </div>

      {/* Логика ProfileNav перенесена сюда */}
      <Link to="/profile" className="profile_nav header-box">
        <div className="profile-link">
          <img 
            src="/images/svg/profile-icon.svg" 
            alt="Profile"
            width="30"
            height="30"
          />
        </div>
      </Link>
    </div>
  );
};

export default Header;