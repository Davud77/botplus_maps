import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useSettings } from '../../utils/mapSettings';
import { workspaceRequest } from '../../utils/workspaceApi';
export default function MapPreferences({ section }: { section: string }) {
  const { user, refreshUser } = useAuth();
  const { data, load } = useSettings();
  const [selected,setSelected]=useState<string|null>(null);
  const [editing,setEditing]=useState(false);
  const [adding,setAdding]=useState(false);
  useEffect(()=>{setSelected(null);setEditing(false);setAdding(false);},[section]);
  const [names,setNames]=useState<Record<string,string>>({});
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
  const first=crs?'EPSG:4326':'osm';
  const items = [...(crs ? data?.coordinate_systems||[] : data?.basemaps||[])].sort((a,b)=>Number(b.id===first)-Number(a.id===first));
  const item=items.find(i=>i.id===selected);
  const current = crs ? data?.defaults.coordinate_system : data?.defaults.basemap;
  return <><section className="table-container ortho-container settings-catalog">
    <div className="ws-section-kicker">НАСТРОЙКИ КАРТ</div><h2>{crs?'Проекции':'Подложки'}</h2>
    <p className="settings-catalog-description">{crs?'Проекция по умолчанию применяется к новым картам. Исходные данные сохраняют свою систему координат.':'Подложка по умолчанию применяется к новым картам. Свои источники можно добавить по URL тайлов.'}</p>
    {notice&&<div className="ws-notice" role="status">{notice}</div>}
    <div className="table-header ortho-header-actions"><div className="action-buttons-group">
      {crs&&admin&&<button className="secondary-button" disabled={!item||pending} onClick={()=>setEditing(v=>!v)}>Редактировать</button>}
      {admin&&<button className="secondary-button" disabled={!item||pending||item.id===current||(crs&&'definition' in item&&!item.definition)} onClick={()=>run(()=>workspaceRequest('/settings/map/defaults','PATCH',crs?{coordinate_system:item!.id}:{basemap:item!.id}))}>По умолчанию</button>}
      <button className="secondary-button" disabled={!item} onClick={()=>setEditing(v=>!v)}>Подробнее</button>
    </div>{admin&&<button className="ws-primary ortho-upload" onClick={()=>setAdding(v=>!v)}>{crs?'Добавить проекцию':'Добавить подложку'}</button>}</div>
    {!data?<p>Загрузка…</p>:<div className="ortho-table-wrapper"><table className="data-table"><thead><tr><th className="col-checkbox" aria-label="Выбор"/><th>{crs?'Проекция':'Подложка'}</th><th>{crs?'Определение':'Источник тайлов'}</th><th>Тип</th><th>По умолчанию</th></tr></thead><tbody>{items.map(row=><tr key={row.id} className={row.id===selected?'selected-row':''}>
      <td><input type="checkbox" aria-label={`Выбрать ${row.name}`} checked={row.id===selected} onChange={()=>{setSelected(selected===row.id?null:row.id);setEditing(false);}}/></td>
      <td data-label={crs?'Проекция':'Подложка'}><div className="ortho-identity"><div className={`settings-catalog-symbol ${crs?'crs':'basemap'}`} aria-hidden="true">{crs?'СК':row.id==='osm'?'OSM':'▧'}</div><div className="ortho-title"><strong>{row.name}</strong><small>{crs?row.id:row.id==='osm'?'OpenStreetMap':'Картографическая подложка'}</small></div></div></td>
      <td data-label={crs?'Определение':'Источник'}><span className="settings-catalog-definition" title={'definition' in row?row.definition:row.url}>{'definition' in row?(row.definition||'Не определено'):row.url||'Без подложки'}</span></td>
      <td data-label="Тип"><span className="settings-catalog-type">{row.builtin?'Встроенная':'Своя'}</span></td><td data-label="По умолчанию">{row.id===current?<span className="ws-badge green">По умолчанию</span>:'—'}</td>
    </tr>)}</tbody></table></div>}
    {editing&&item&&<section className="ortho-editor ws-card"><h3>{item.name}</h3>
      {crs&&'definition' in item?<>
        {admin&&<><label>Название проекции<input aria-label={`Название проекции ${item.name}`} maxLength={120} value={names[item.id]??item.name} onChange={e=>setNames({...names,[item.id]:e.target.value})}/></label><button className="ws-secondary" disabled={pending||!(names[item.id]??item.name).trim()||(names[item.id]??item.name).trim()===item.name} onClick={()=>run(()=>workspaceRequest(`/settings/coordinate-systems/${encodeURIComponent(item.id)}`,'PATCH',{name:(names[item.id]??item.name).trim()}))}>Сохранить название</button></>}
        <details><summary>Определение</summary><pre>{item.definition||'Определение неизвестно.'}</pre>{admin&&!item.builtin&&<><textarea aria-label={`Определение ${item.name}`} rows={4} value={edits[item.id]??item.definition} onChange={e=>setEdits({...edits,[item.id]:e.target.value})}/><button className="ws-secondary" disabled={pending||!(edits[item.id]??item.definition).trim()} onClick={()=>run(()=>workspaceRequest(`/settings/coordinate-systems/${encodeURIComponent(item.id)}`,'PATCH',{definition:edits[item.id]??item.definition}))}>Сохранить определение</button></>}</details>
      </>: 'url' in item&&<><p className="settings-catalog-url">{item.url||'Без подложки'}</p><p>Схема: {item.scheme.toUpperCase()} · Масштаб до {item.max_zoom}</p><p>{item.attribution}</p></>}
      <button className="ws-secondary" onClick={()=>setEditing(false)}>Закрыть</button>
    </section>}
  </section>{admin && adding && <section className="ws-card"><h2>{crs ? 'Добавить проекцию' : 'Добавить подложку'}</h2><form className="ws-form-narrow" onSubmit={event => { event.preventDefault(); run(async () => { await workspaceRequest(crs ? '/settings/coordinate-systems' : '/settings/basemaps','POST',crs ? {name,definition} : {name,url,attribution,scheme,max_zoom:zoom}); setName(''); setDefinition(''); setUrl(''); setAttribution(''); }); }}>
    <label htmlFor="catalog-name">Название</label><input id="catalog-name" required maxLength={120} value={name} onChange={e => setName(e.target.value)} />
    {crs ? <><label htmlFor="crs-definition">EPSG, WKT или PROJ</label><textarea id="crs-definition" required maxLength={16000} rows={5} placeholder="EPSG:32638 или +proj=tmerc …" value={definition} onChange={e => setDefinition(e.target.value)} /></> : <><label htmlFor="basemap-url">URL тайлов</label><input id="basemap-url" required placeholder="http://localhost:8080/tiles/{z}/{x}/{y}.png" value={url} onChange={e => setUrl(e.target.value)} /><label htmlFor="basemap-attribution">Подпись источника</label><input id="basemap-attribution" maxLength={300} value={attribution} onChange={e => setAttribution(e.target.value)} /><label htmlFor="basemap-scheme">Схема</label><select id="basemap-scheme" value={scheme} onChange={e => setScheme(e.target.value)}><option value="xyz">XYZ</option><option value="tms">TMS</option></select><label htmlFor="basemap-zoom">Максимальный масштаб</label><input id="basemap-zoom" type="number" min={0} max={24} value={zoom} onChange={e => setZoom(+e.target.value)} /></>}
    <button className="ws-primary" disabled={pending}>{pending ? 'Сохраняем…' : 'Добавить'}</button></form></section>}</>;
}
