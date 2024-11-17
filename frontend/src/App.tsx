import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './components/Home';
import UploadPano from './components/UploadPano';
import MapPage from './components/maps/MapPage';
import LoginPage from './components/LoginPage';
import ProfilePage from './components/ProfilePage';
import UploadOrtho from './components/UploadOrtho';
import './assets/css/styles.css';
import { useAuth } from './hooks/useAuth';

const App: React.FC = () => {
  const { isAuthenticated, login } = useAuth();

  useEffect(() => {
    const auth = localStorage.getItem('auth') === 'true';
    if (auth) {
      login();
    }
  }, [login]);

  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true, // Изменено здесь
      }}
    >
      <Routes>
        <Route
          path="/"
          element={isAuthenticated ? <Home /> : <Navigate replace to="/login" />}
        />
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate replace to="/" /> : <LoginPage />}
        />
        <Route
          path="/upload"
          element={isAuthenticated ? <UploadPano /> : <Navigate replace to="/login" />}
        />
        <Route
          path="/map"
          element={isAuthenticated ? <MapPage /> : <Navigate replace to="/login" />}
        />
        <Route
          path="/profile"
          element={isAuthenticated ? <ProfilePage /> : <Navigate replace to="/login" />}
        />
        <Route
          path="/uploadortho"
          element={isAuthenticated ? <UploadOrtho /> : <Navigate replace to="/login" />}
        />
      </Routes>
    </BrowserRouter>
  );
};

export default App;