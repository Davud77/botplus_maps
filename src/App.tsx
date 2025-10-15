// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './components/Home';
import MapPage from './components/maps/MapPage';
import LoginPage from './components/LoginPage';
import ProfilePage from './components/ProfilePage';
import UploadOrtho from './components/UploadOrtho';
import UploadPano from './components/UploadPano';
import { useAuth } from './hooks/useAuth';
import './index.css';

const App: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="loading-screen">Проверка авторизации...</div>;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={isAuthenticated ? <Home /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />
        <Route
          path="/map"
          element={isAuthenticated ? <MapPage /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/profile"
          element={isAuthenticated ? <ProfilePage /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/upload"
          element={isAuthenticated ? <UploadPano /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/uploadortho"
          element={isAuthenticated ? <UploadOrtho /> : <Navigate to="/login" replace />}
        />
        <Route path="*" element={<Navigate to={isAuthenticated ? "/" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;