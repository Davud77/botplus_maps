import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './SetupPage.css';
import { API_BASE } from '../utils/api';

export default function SetupPage() {
  const { completeSetup } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [closed, setClosed] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    if (password !== confirmation) { setError('Пароли не совпадают.'); return; }
    setPending(true); setError('');
    try {
      const response = await fetch(`${API_BASE}/api/setup/initialize`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const result = await response.json();
      if (response.status === 409) setClosed(true);
      if (!response.ok) throw new Error(result.message || 'Не удалось создать аккаунт.');
      completeSetup(); navigate('/', { replace: true });
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Сервер недоступен. Повторите попытку.');
    } finally { setPending(false); }
  }

  return <main className="setup-shell">
    <aside className="setup-intro">
      <a className="setup-brand" href="/"> <span className="setup-brand-icon">B+</span> BotPlus Maps</a>
      <div className="setup-intro-copy">
        <span className="setup-eyebrow">ВАША ГЕОПЛАТФОРМА</span>
        <h1>Ваши карты.<br />Ваши данные.<br /><em>Ваши правила.</em></h1>
        <p>Собственное пространство для ортофотопланов, панорам и векторных слоёв. На вашей инфраструктуре.</p>
        <div className="setup-terrain" aria-hidden="true"><i /><i /><i /><i /><b>+ 42.97° N · 47.50° E</b></div>
      </div>
      <footer>SELF-HOSTED GIS <span>Открытый код · AGPL-3.0</span></footer>
    </aside>
    <section className="setup-panel" aria-labelledby="setup-title">
      <div className="setup-card">
        <div className="setup-step"><span>1</span> Первый запуск <b>Настройка аккаунта</b></div>
        <h2 id="setup-title">Добро пожаловать</h2>
        <p className="setup-subtitle">Создайте аккаунт администратора, чтобы начать работу с вашей геоплатформой.</p>
        <form onSubmit={submit} aria-busy={pending}>
          <label htmlFor="setup-username">Логин администратора</label>
          <input id="setup-username" name="username" autoComplete="username" autoFocus required minLength={3} maxLength={50} pattern="[a-zA-Z0-9_.\-]{3,50}" placeholder="Например, davud" value={username} disabled={pending || closed} onChange={e => setUsername(e.target.value)} aria-describedby="setup-username-hint" />
          <small id="setup-username-hint">3–50 символов: латинские буквы, цифры, . _ -</small>
          <label htmlFor="setup-password">Пароль</label>
          <div className="setup-password"><input id="setup-password" name="password" type={visible ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} placeholder="Не менее 12 символов" value={password} disabled={pending || closed} onChange={e => setPassword(e.target.value)} /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}>{visible ? 'Скрыть' : 'Показать'}</button></div>
          <label htmlFor="setup-confirmation">Повторите пароль</label>
          <input id="setup-confirmation" name="confirmation" type={visible ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} placeholder="Введите пароль ещё раз" value={confirmation} disabled={pending || closed} onChange={e => setConfirmation(e.target.value)} />
          {error && <p className="setup-error" role="alert">{error}</p>}
          {closed ? <a className="setup-submit" href="/login">Перейти ко входу →</a> : <button className="setup-submit" disabled={pending} type="submit">{pending ? 'Создаём аккаунт…' : 'Создать аккаунт и начать'} <span aria-hidden="true">→</span></button>}
        </form>
        <div className="setup-note"><span aria-hidden="true">⌁</span><p>Этот мастер доступен только до создания первого аккаунта. Сохраните логин и пароль в надёжном месте.</p></div>
      </div>
      <footer className="setup-panel-footer">Данные остаются под вашим контролем.</footer>
    </section>
  </main>;
}
