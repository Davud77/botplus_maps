import React from 'react';
import Header from './Header';

const Home: React.FC = () => {
  return (
    <div 
      className="home-container" 
      style={{ backgroundImage: "url('/images/background.png')" }}
    >
      <Header />
      <div className="version">
        0.2.5
      </div>
    </div>
  );
};

export default Home;