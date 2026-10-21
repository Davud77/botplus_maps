import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './workspace/Workspace.css';
export default function Header() {
  const { user } = useAuth();
  return <header className="ws-header">
    <Link className="ws-brand" to="/"><span>B+</span>BotPlus Maps</Link>
    <nav aria-label="Основная навигация"><NavLink to="/" end>Рабочее пространство</NavLink><NavLink to="/profile">Данные и настройки</NavLink></nav>
    <Link to="/profile" className="ws-account"><span className="ws-avatar">{user?.username.slice(0, 2).toUpperCase()}</span><span>{user?.username}</span></Link>
  </header>;
}
