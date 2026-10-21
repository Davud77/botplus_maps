import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import AuthLayout from './workspace/AuthLayout';
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setError('');
    try {
      if (await login(username, password)) navigate('/', { replace: true });
      else setError('Не удалось войти. Проверьте логин, пароль и доступность аккаунта.');
    } catch { setError('Сервер недоступен. Повторите попытку.'); }
    finally { setPending(false); }
  }
  return <AuthLayout title="Вход в аккаунт"><div className="setup-card">
    <div className="setup-step"><span>↗</span> Ваше рабочее пространство</div>
    <h2>С возвращением</h2><p className="setup-subtitle">Войдите, чтобы продолжить работу с картами и данными вашей организации.</p>
    <form onSubmit={submit} aria-busy={pending}>
      <label htmlFor="login-username">Логин</label><input id="login-username" autoComplete="username" autoFocus required maxLength={50} value={username} onChange={e => setUsername(e.target.value)} disabled={pending} placeholder="Ваш логин" />
      <label htmlFor="login-password">Пароль</label><div className="setup-password"><input id="login-password" type={visible ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} disabled={pending} placeholder="Ваш пароль" /><button type="button" aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} onClick={() => setVisible(!visible)}>{visible ? 'Скрыть' : 'Показать'}</button></div>
      {error && <p className="setup-error" role="alert">{error}</p>}
      <button className="setup-submit" disabled={pending}>{pending ? 'Входим…' : 'Войти в пространство'} <span aria-hidden="true">→</span></button>
    </form><div className="setup-note"><span aria-hidden="true">⌁</span><p>Доступ и восстановление аккаунта — у администратора вашей установки.</p></div>
  </div></AuthLayout>;
}
