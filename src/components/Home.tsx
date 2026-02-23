import React from 'react';
import Header from './Header';

const Home: React.FC = () => {
  return (
    <div className="home-container">
      <Header />
      <div className="version">
        0.0.1
      </div>
    </div>
  );
};

export default Home;