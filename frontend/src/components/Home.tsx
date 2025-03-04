// src/components/Home.tsx
import React from 'react';
import Header from './Header';

const Home: React.FC = () => {
  return (
    <div className="background full-screen-video">
      <Header />
      <video autoPlay loop muted style={{ position: 'absolute', width: '100vw', height: '100vh', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', objectFit: 'cover' }}>
        <source src="/videos/banner.mp4" type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default Home;