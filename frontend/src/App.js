// Файл: src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Home from './Home';
import UploadPage from './UploadPage';
import MapPage from './MapPage';
import LoginPage from './LoginPage';
import ProfilePage from './ProfilePage';
import './styles.css';

function App() {
  const isAuthenticated = sessionStorage.getItem('auth');

  return (
    <Router>
      <Routes>
        <Route path="/" element={isAuthenticated ? <Home /> : <Navigate replace to="/login" />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/upload" element={isAuthenticated ? <UploadPage /> : <Navigate replace to="/login" />} />
        <Route path="/map" element={isAuthenticated ? <MapPage /> : <Navigate replace to="/login" />} />
        <Route path="/profile" element={isAuthenticated ? <ProfilePage /> : <Navigate replace to="/login" />} />
      </Routes>
    </Router>
  );
}

export default App;
