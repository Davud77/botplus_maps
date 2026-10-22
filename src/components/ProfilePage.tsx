import { useSearchParams } from 'react-router-dom';
import React, { useCallback, useEffect, useState } from 'react';
import Header from './Header';
import MapPreferences from './profile/MapPreferences';
import ImportJobs from './profile/ImportJobs';
import TasksPanel from './profile/TasksPanel';
import { useAuth } from '../hooks/useAuth';
import { Role, roleNames, WorkspaceUser, workspaceRequest } from '../utils/workspaceApi';
import ProfileVector from './profile/ProfileVector';
import ProfilePanoramas from './profile/ProfilePanoramas';
import ProfileOrthophotos from './profile/ProfileOrthophotos';
import './workspace/Workspace.css';

export default function ProfilePage() {
  const { user, logout, refreshUser } = useAuth();
  const [params,setParams]=useSearchParams();
  const tab=params.get('section')||'account';
  const setTab=(value:string)=>setParams({section:value});
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<Role>('viewer');
  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try { setUsers((await workspaceRequest<{ users: WorkspaceUser[] }>('/users')).users); }
    catch (e) { setNotice({ text: (e as Error).message, error: true }); }
    finally { setUsersLoading(false); }
  }, []);
  useEffect(() => { if (tab === 'users' && user?.role === 'admin') { loadUsers(); } }, [tab, user?.role, loadUsers]);
  async function changePassword(event: React.FormEvent) {
    event.preventDefault(); if (pending) return;
    if (password !== confirmation) { setNotice({ text: 'Пароли не совпадают.', error: true }); return; }
    setPending(true); setNotice(null);
    try {
      const result = await workspaceRequest<{ message: string }>('/account/password', 'POST', { current_password: current, new_password: password });
      setCurrent(''); setPassword(''); setConfirmation(''); setNotice({ text: result.message, error: false });
    } catch (e) { setNotice({ text: (e as Error).message, error: true }); } finally { setPending(false); }
  }
  async function createUser(event: React.FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setNotice(null);
    try {
      await workspaceRequest('/users','POST',{ username: newUsername, password: newPassword, role: newRole });
      setNewUsername(''); setNewPassword(''); setNewRole('viewer'); await loadUsers();
      setNotice({ text: 'Пользователь создан. Передайте ему реквизиты безопасным способом.', error: false });
    } catch (e) { setNotice({ text: (e as Error).message, error: true }); } finally { setPending(false); }
  }
  async function updateUser(id: number, changes: Partial<WorkspaceUser>) {
    if (pending) return; setPending(true); setNotice(null);
    try {
      const result = await workspaceRequest<{ user: WorkspaceUser }>(`/users/${id}`, 'PATCH', changes);
      setUsers(previous => previous.map(item => item.id === id ? result.user : item));
      setNotice({ text: 'Права пользователя обновлены.', error: false });
      if (id === user?.id) { const me = await refreshUser(); if (me?.role !== 'admin') setTab('account'); }
    } catch (e) { setNotice({ text: (e as Error).message, error: true }); } finally { setPending(false); }
  }
  const groups = [
    { title: 'Личное', items: [['account','Аккаунт'],['security','Безопасность'],['appearance','Оформление']] },
    ...(user?.role === 'admin' ? [{ title: 'Команда', items: [['users','Пользователи']] }] : []),
    { title: 'Настройки карт', items: [['crs','Проекции'],['basemaps','Подложки']] },
    { title: 'Геоданные', items: [...(user?.role !== 'viewer' ? [['imports','Импорт'],['tasks','Задания']] : []),['ortho','Ортофотопланы'],['panoramas','Панорамы'],['vector','Векторные данные']] },
  ];
  return <div className="ws-shell"><Header /><main className="ws-main">
    <div className="ws-eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</div><div className="ws-page-heading"><div><h1>Данные и настройки</h1><p>Управляйте своим аккаунтом, доступом команды и геоданными.</p></div></div>
    <div className="ws-profile-layout"><aside className="ws-sidebar"><div className="ws-person"><span className="ws-avatar large">{user?.username.slice(0,2).toUpperCase()}</span><strong>{user?.username}</strong><span>{user && roleNames[user.role]}</span></div>
      <nav aria-label="Разделы профиля">{groups.map(group => <div className="ws-nav-group" key={group.title} role="group" aria-label={group.title}><h2 className="ws-nav-group-title">{group.title}</h2>{group.items.map(([key,label]) => <button key={key} className={tab === key ? 'active' : ''} aria-current={tab === key ? 'page' : undefined} onClick={() => { setTab(key); setNotice(null); }}>{label}<span aria-hidden="true">›</span></button>)}</div>)}</nav>
      <button className="ws-logout" onClick={() => logout()}>Выйти из аккаунта ↗</button>
    </aside><section className="ws-profile-content">
      {notice && <div className={`ws-notice ${notice.error ? 'ws-error' : ''}`} role={notice.error ? 'alert' : 'status'}>{notice.text}</div>}
      {tab==='imports' && user?.role!=='viewer' && <ImportJobs key={params.toString()} />}
      {tab==='tasks' && user?.role!=='viewer' && <TasksPanel />}
      {['appearance','crs','basemaps'].includes(tab) && <MapPreferences key={tab} section={tab} />}
      {tab === 'account' && <><section className="ws-card"><div className="ws-section-kicker">АККАУНТ</div><h2>Личная информация</h2><p>Ваш аккаунт в этой установке BotPlus Maps.</p><dl className="ws-details"><div><dt>Логин</dt><dd>{user?.username}</dd></div><div><dt>Роль</dt><dd>{user && roleNames[user.role]}</dd></div><div><dt>Размещение</dt><dd>Собственная инфраструктура</dd></div></dl></section><section className="ws-card ws-accent-card"><h2>Всё начинается с карты</h2><p>Объединяйте слои в проекты и публикуйте только то, чем хотите поделиться.</p><a href="/">Перейти к картам →</a></section></>}
      {tab === 'security' && <section className="ws-card"><div className="ws-section-kicker">БЕЗОПАСНОСТЬ</div><h2>Сменить пароль</h2><p>После смены пароля остальные сеансы вашего аккаунта завершатся.</p><form className="ws-form-narrow" onSubmit={changePassword}>
        <label htmlFor="current-password">Текущий пароль</label><input id="current-password" type="password" autoComplete="current-password" value={current} required onChange={e => setCurrent(e.target.value)} disabled={pending} />
        <label htmlFor="new-password">Новый пароль</label><input id="new-password" type="password" autoComplete="new-password" value={password} minLength={12} maxLength={128} required onChange={e => setPassword(e.target.value)} disabled={pending} /><small>От 12 до 128 символов. Пробелы являются частью пароля.</small>
        <label htmlFor="confirm-password">Повторите новый пароль</label><input id="confirm-password" type="password" autoComplete="new-password" value={confirmation} minLength={12} maxLength={128} required onChange={e => setConfirmation(e.target.value)} disabled={pending} />
        <button className="ws-primary" disabled={pending}>{pending ? 'Сохраняем…' : 'Изменить пароль'}</button></form></section>}
      {tab === 'users' && user?.role === 'admin' && <><section className="ws-card"><div className="ws-section-kicker">КОМАНДА</div><h2>Создать пользователя</h2><p>Наблюдатель просматривает данные. Редактор работает с данными и своими картами. Администратор управляет всей установкой.</p>
        <form className="ws-user-form" onSubmit={createUser}><div><label htmlFor="new-username">Логин</label><input id="new-username" autoComplete="off" required minLength={3} maxLength={50} pattern="[a-zA-Z0-9_.\-]{3,50}" value={newUsername} onChange={e => setNewUsername(e.target.value)} disabled={pending} /></div><div><label htmlFor="user-password">Начальный пароль</label><input id="user-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={e => setNewPassword(e.target.value)} disabled={pending} /></div><div><label htmlFor="user-role">Роль</label><select id="user-role" value={newRole} onChange={e => setNewRole(e.target.value as Role)} disabled={pending}>{Object.entries(roleNames).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></div><button className="ws-primary" disabled={pending}>{pending ? 'Создаём…' : 'Создать пользователя'}</button></form></section>
        <section className="ws-card"><h2>Пользователи пространства</h2><p>Изменения ролей применяются к следующим запросам пользователя.</p>{usersLoading ? <p role="status">Загрузка…</p> : <div className="ws-users">{users.map(item => <div className="ws-user-row" key={item.id}><span className="ws-avatar">{item.username.slice(0,2).toUpperCase()}</span><div><strong>{item.username}{item.id === user.id ? ' · вы' : ''}</strong><small>{item.is_active ? 'Активен' : 'Отключён'}</small></div><select aria-label={`Роль ${item.username}`} value={item.role} disabled={pending} onChange={e => updateUser(item.id, { role: e.target.value as Role })}>{Object.entries(roleNames).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select><button className="ws-secondary" disabled={pending} onClick={() => updateUser(item.id, { is_active: !item.is_active })}>{item.is_active ? 'Отключить' : 'Включить'}</button></div>)}</div>}</section></>}
      {['vector','panoramas','ortho'].includes(tab) && <section className="ws-card ws-legacy">{user?.role === 'viewer' && <p className="ws-notice">Ваша роль разрешает только просмотр. Изменения доступны редактору и администратору.</p>}{tab === 'vector' && <ProfileVector />}{tab === 'panoramas' && <ProfilePanoramas />}{tab === 'ortho' && <ProfileOrthophotos />}</section>}
    </section></div>
  </main></div>;
}
