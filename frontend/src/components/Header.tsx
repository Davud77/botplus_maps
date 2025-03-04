// src/components/Header.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import ProfileNav from './ProfileNav';

const Header: React.FC = () => {
  return (
    <div className="navigation-menu">
      <div className="logo-menu">
        <Link to="/" className="logo">
          {/* В качестве fallback-текста можно оставить название или убрать совсем */}
          <img src="/images/logo.png" alt="Логотип" />
        </Link>
        <Link to="/map">
          <button className="button button_nav">Карты</button>
        </Link>
      </div>

      <ProfileNav />
    </div>
  );
};

export default Header;