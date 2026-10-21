import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Header from './Header';
import { useAuth } from '../hooks/useAuth';
import { MapDocument, workspaceRequest } from '../utils/workspaceApi';
import './workspace/Workspace.css';

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [maps, setMaps] = useState<MapDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [pending, setPending] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true); setError('');
    const timer = window.setTimeout(() => {
      workspaceRequest<{ maps: MapDocument[]; total: number }>(`/maps?q=${encodeURIComponent(query)}&status=${filter}&offset=${offset}`)
        .then(result => { if (live) { setMaps(result.maps); setTotal(result.total); } })
        .catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setLoading(false); });
    }, 180);
    return () => { live = false; window.clearTimeout(timer); };
  }, [query, filter, offset, reload]);
  async function create(event: React.FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setError('');
    try {
      const result = await workspaceRequest<{ map: MapDocument }>('/maps', 'POST', { title, description });
      navigate(`/maps/${result.map.id}`);
    } catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  return <div className="ws-shell"><Header /><main className="ws-main">
    <div className="ws-eyebrow">ВАШЕ РАБОЧЕЕ ПРОСТРАНСТВО</div>
    <div className="ws-page-heading"><div><h1>Карты и проекты</h1><p>Собирайте данные в карты. Делитесь результатами на своих условиях.</p></div>
      {user?.role !== 'viewer' && <button className="ws-primary" onClick={() => { setCreating(!creating); setError(''); }}>＋ Создать карту</button>}
    </div>
    {creating && <section className="ws-card ws-create"><h2>Новая карта</h2><p>Карта сохранится в вашем пространстве. Публикацию можно включить позже.</p>
      <form onSubmit={create}><label htmlFor="map-title">Название карты</label><input id="map-title" autoFocus required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} placeholder="Например, Мониторинг строительства" disabled={pending} />
        <label htmlFor="map-description">Описание <span className="ws-muted">· необязательно</span></label><textarea id="map-description" maxLength={1000} value={description} onChange={e => setDescription(e.target.value)} disabled={pending} placeholder="Что показывает эта карта?" />
        <div className="ws-actions"><button className="ws-primary" disabled={pending}>{pending ? 'Создаём…' : 'Создать и открыть'}</button><button className="ws-secondary" type="button" onClick={() => setCreating(false)} disabled={pending}>Отмена</button></div>
      </form></section>}
    <div className="ws-toolbar"><div className="ws-tabs" aria-label="Фильтр карт">{[['all','Все карты'],['published','Опубликованные'],['private','Внутренние']].map(([value,label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? 'active' : ''} onClick={() => { setFilter(value); setOffset(0); }}>{label}</button>)}</div>
      <input className="ws-search" aria-label="Поиск карт" placeholder="Поиск по названию и описанию" value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }} /></div>
    {error && <div className="ws-notice ws-error" role="alert">{error} <button onClick={() => setReload(reload + 1)}>Повторить</button></div>}
    {loading ? <div className="ws-empty" role="status">Загружаем карты…</div> : !error && maps.length === 0 ? <div className="ws-empty"><div className="ws-empty-symbol">▱</div><h2>{query || filter !== 'all' ? 'Карт не найдено' : 'Здесь начнётся ваша первая карта'}</h2><p>{user?.role === 'viewer' ? 'Карты появятся, когда их создаст редактор или администратор.' : 'Создайте карту, добавьте слои и сохраните нужный ракурс.'}</p>{user?.role !== 'viewer' && !creating && <button className="ws-primary" onClick={() => setCreating(true)}>＋ Создать первую карту</button>}</div> : <div className="ws-map-grid">{maps.map(map => <article key={map.id} className="ws-map-card">
      <Link to={`/maps/${map.id}`} className="ws-map-cover" aria-label={`Открыть карту ${map.title}`}><div className="ws-map-art" aria-hidden="true"><i /><i /><i /><b>＋</b></div><span className={`ws-badge ${map.published ? 'green' : ''}`}>{map.published ? 'Опубликована' : 'Внутренняя'}</span></Link>
      <div className="ws-map-info"><h2><Link to={`/maps/${map.id}`}>{map.title}</Link></h2><p>{map.description || 'Добавьте слои и настройте карту под свою задачу.'}</p><div className="ws-map-meta"><span>{map.owner_name}</span><span>{new Date(map.updated_at).toLocaleDateString('ru-RU')}</span></div><div className="ws-map-links"><Link to={`/maps/${map.id}`}>{map.can_edit ? 'Открыть редактор' : 'Открыть карту'} →</Link>{map.public_slug && <Link to={`/p/${map.public_slug}`} target="_blank" rel="noreferrer">Публикация ↗</Link>}</div></div>
    </article>)}</div>}
    {!loading && total > 0 && <div className="ws-pagination"><span>Показано {offset + 1}–{Math.min(offset + maps.length,total)} из {total}</span><button className="ws-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0,offset-48))}>Назад</button><button className="ws-secondary" disabled={offset + maps.length >= total} onClick={() => setOffset(offset+48)}>Далее</button></div>}
    <footer className="ws-footer">BotPlus Maps · 0.3.4.1 <span>Ваши данные. Ваша инфраструктура.</span></footer>
  </main></div>;
}
