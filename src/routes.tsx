import { RouteObject } from 'react-router-dom';
import MapPage from './components/maps/MapPage';
import Home from './components/Home';
import ProfilePage from './components/ProfilePage';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Home />, // Главная страница
  },
  {
    path: '/map',
    element: <MapPage />,
  },
  {
    path: '/profile',
    element: <ProfilePage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },

];
