import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useSettings } from '../../utils/mapSettings';
import { workspaceRequest } from '../../utils/workspaceApi';
export default function MapPreferences({ section }: { section: string }) {
  const { user, refreshUser } = useAuth();
  const { data, load } = useSettings();
  const [edits,setEdits]=useState<Record<string,string>>({});
  const [name,setName] = useState(''); const [definition,setDefinition] = useState('');
  const [url,setUrl] = useState(''); const [attribution,setAttribution] = useState('');
  const [scheme,setScheme] = useState('xyz'); const [zoom,setZoom] = useState(22);
  const [notice,setNotice] = useState(''); const [pending,setPending] = useState(false);
  const admin = user?.role === 'admin';
  useEffect(() => { load().catch(e => setNotice(e.message)); }, [load]);
  async function run(action: () => Promise<unknown>) {
    setPending(true); setNotice(''); try { await action(); await load(); setNotice('Настройки сохранены.'); } catch(e) { setNotice((e as Error).message); } finally { setPending(false); }
  }
  if (section === 'appearance') return <section className="ws-card"><div className="ws-section-kicker">ИНТЕРФЕЙС</div><h2>Оформление</h2><p>Тема сохраняется в вашем аккаунте и применяется ко всему приложению.</p><div className="ws-actions">{(['light','dark'] as const).map(theme => <button key={theme} className={user?.theme === theme ? 'ws-primary' : 'ws-secondary'} disabled={pending} onClick={() => run(async () => { await workspaceRequest('/account/preferences','PATCH',{theme}); await refreshUser(); })}>{theme === 'light' ? '☀ Светлая' : '☾ Тёмная'}</button>)}</div>{notice && <p role="status">{notice}</p>}</section>;
  const crs = section === 'crs';
  const items = crs ? data?.coordinate_systems : data?.basemaps;
  const current = crs ? data?.defaults.coordinate_system : data?.defaults.basemap;
  return <><section className="ws-card"><div className="ws-section-kicker">НАСТРОЙКИ КАРТ</div><h2>{crs ? 'Проекции' : 'Подложки'}</h2><p>{crs ? 'СК по умолчанию используется для отображения координат новых карт. Определения принимаются в EPSG, WKT и PROJ. Карта с веб-подложками отображается в Web Mercator; исходные данные хранят свою СК.' : 'Подложка по умолчанию применяется к новым картам. Собственные XYZ и TMS источники появятся в редакторе. Внешние подложки загружаются браузером с сервера провайдера; для автономной работы добавьте локальный источник или выберите «Без подложки».'}</p>
    {notice && <div className="ws-notice" role="status">{notice}</div>}
    {!data ? <p>Загрузка…</p> : <div className="bp-catalog">{items?.map(item => <div className="bp-catalog-row" key={item.id}><div><strong>{item.name}</strong><small>{item.builtin ? 'Встроенная' : 'Своя'}{item.id === current ? ' · по умолчанию' : ''}</small>{crs && <details><summary>Определение</summary><pre>{'definition' in item ? item.definition || 'Определение неизвестно. Положение на карте не угадывается.' : ''}</pre>{admin&&!item.builtin&&<><textarea aria-label={`Определение ${item.name}`} rows={3} value={edits[item.id]??('definition' in item?item.definition:'')} onChange={e=>setEdits({...edits,[item.id]:e.target.value})}/><button className="ws-secondary" disabled={pending||!(edits[item.id]??('definition' in item?item.definition:'')).trim()} onClick={()=>run(()=>workspaceRequest(`/settings/coordinate-systems/${encodeURIComponent(item.id)}`,'PATCH',{definition:edits[item.id]??('definition' in item?item.definition:'')}))}>Сохранить определение</button></>}</details>}</div>{admin && <button className="ws-secondary" disabled={pending || item.id === current || (crs && 'definition' in item && !item.definition)} onClick={() => run(() => workspaceRequest('/settings/map/defaults','PATCH',crs ? {coordinate_system:item.id} : {basemap:item.id}))}>{item.id === current ? 'Выбрано' : 'По умолчанию'}</button>}</div>)}</div>}
  </section>{admin && <section className="ws-card"><h2>{crs ? 'Добавить проекцию' : 'Добавить подложку'}</h2><form className="ws-form-narrow" onSubmit={event => { event.preventDefault(); run(async () => { await workspaceRequest(crs ? '/settings/coordinate-systems' : '/settings/basemaps','POST',crs ? {name,definition} : {name,url,attribution,scheme,max_zoom:zoom}); setName(''); setDefinition(''); setUrl(''); setAttribution(''); }); }}>
    <label htmlFor="catalog-name">Название</label><input id="catalog-name" required maxLength={120} value={name} onChange={e => setName(e.target.value)} />
    {crs ? <><label htmlFor="crs-definition">EPSG, WKT или PROJ</label><textarea id="crs-definition" required maxLength={16000} rows={5} placeholder="EPSG:32638 или +proj=tmerc …" value={definition} onChange={e => setDefinition(e.target.value)} /></> : <><label htmlFor="basemap-url">URL тайлов</label><input id="basemap-url" required placeholder="http://localhost:8080/tiles/{z}/{x}/{y}.png" value={url} onChange={e => setUrl(e.target.value)} /><label htmlFor="basemap-attribution">Подпись источника</label><input id="basemap-attribution" maxLength={300} value={attribution} onChange={e => setAttribution(e.target.value)} /><label htmlFor="basemap-scheme">Схема</label><select id="basemap-scheme" value={scheme} onChange={e => setScheme(e.target.value)}><option value="xyz">XYZ</option><option value="tms">TMS</option></select><label htmlFor="basemap-zoom">Максимальный масштаб</label><input id="basemap-zoom" type="number" min={0} max={24} value={zoom} onChange={e => setZoom(+e.target.value)} /></>}
    <button className="ws-primary" disabled={pending}>{pending ? 'Сохраняем…' : 'Добавить'}</button></form></section>}</>;
}
