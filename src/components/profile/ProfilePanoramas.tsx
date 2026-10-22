import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, useMap } from 'react-leaflet';
import { useAuth } from '../../hooks/useAuth';
import { workspaceRequest } from '../../utils/workspaceApi';
import PanoLayer from '../maps/layers/PanoLayer';
import PanoramaViewer from '../maps/ui/viewers/PanoramaViewer';
interface Item {id:number;name:string;folder_id:number|null;tags:string;latitude:number;longitude:number;media_type:string|null;}
interface Folder {id:number;name:string;}
function CatalogBounds({query,onError}:{query:string;onError:(text:string)=>void}) {
  const map=useMap();
  useEffect(()=>{let live=true;workspaceRequest<{bounds:{west:number;south:number;east:number;north:number}|null}>(`/media/bounds?${query}`).then(({bounds:b})=>{if(live&&b)map.fitBounds([[b.south,b.west],[b.north,b.east]],{padding:[24,24],maxZoom:18});}).catch(e=>{if(live)onError(e.message);});return()=>{live=false;};},[map,query,onError]);
  return null;
}
export default function ProfilePanoramas() {
  const {user}=useAuth();const editable=user?.role!=='viewer';
  const [items,setItems]=useState<Item[]>([]);const [folders,setFolders]=useState<Folder[]>([]);
  const [trash,setTrash]=useState(false);
  const [view,setView]=useState('list');const [selected,setSelected]=useState<Set<number>>(new Set());
  const [cursor,setCursor]=useState<number[]>([0]);const [next,setNext]=useState<number|null>(null);
  const [destination,setDestination]=useState('');const [tags,setTags]=useState('');
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [loading,setLoading]=useState(false);const [pending,setPending]=useState(false);const [revision,setRevision]=useState(0);const [preview,setPreview]=useState<string|null>(null);
  const query=useMemo(()=>new URLSearchParams({trash:trash?'1':'0'}).toString(),[trash]);
  useEffect(()=>{setCursor([0]);setSelected(new Set());setPreview(null);},[query]);
  const after=cursor[cursor.length-1];
  useEffect(()=>{let live=true;setLoading(true);workspaceRequest<{items:Item[];next_cursor:number|null}>(`/media/catalog?${query}&after=${after}`).then(value=>{if(live){setItems(value.items);setNext(value.next_cursor);}}).catch(e=>{if(live)setError(e.message);}).finally(()=>{if(live)setLoading(false);});return()=>{live=false;};},[query,after,revision]);
  const loadFolders=useCallback(async()=>setFolders((await workspaceRequest<{folders:Folder[]}>('/media/folders')).folders),[]);
  useEffect(()=>{loadFolders().catch(e=>setError(e.message));},[loadFolders]);
  async function run(action:()=>Promise<unknown>,message:string) {setPending(true);setError('');setNotice('');try{await action();setNotice(message);setSelected(new Set());setRevision(r=>r+1);await loadFolders();}catch(e){setError((e as Error).message);}finally{setPending(false);}}
  const bulk=(action:string,extra={})=>run(()=>workspaceRequest('/media/bulk','POST',{ids:[...selected],action,...extra}),action==='trash'?'Выбранные файлы перемещены в корзину. Исходники и копии сохранены.':action==='restore'?'Файлы восстановлены.':'Изменения сохранены.');
  const pageSelected=items.length>0&&items.every(i=>selected.has(i.id));
  return <div className="ws-media-catalog"><div className="ws-media-toolbar">
    <div className="ws-tabs" aria-label="Вид каталога"><button className={view==='list'?'active':''} onClick={()=>setView('list')}>Список</button><button className={view==='map'?'active':''} onClick={()=>setView('map')}>Карта</button></div>
    {editable&&<Link className="ws-primary" to="/profile?section=imports&type=panoramas&mode=upload">Импортировать</Link>}
    </div>
    {error&&<p className="ws-notice ws-error" role="alert">{error}</p>}{notice&&<p className="ws-notice" role="status">{notice}</p>}
    {view==='list'?<>{editable&&<div className="ws-media-bulk"><strong>Выбрано: {selected.size} / 500</strong><button className="ws-secondary" disabled={pending} onClick={()=>setTrash(value=>!value)}>{trash?'Все файлы':'Открыть корзину'}</button><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>setSelected(new Set())}>Снять выбор</button><select aria-label="Папка назначения" value={destination} onChange={e=>setDestination(e.target.value)}><option value="">Без папки</option>{folders.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk('move',{folder_id:destination?+destination:null})}>Переместить</button><input aria-label="Теги выбранных файлов" placeholder="Теги выбранных…" maxLength={2000} value={tags} onChange={e=>setTags(e.target.value)} /><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk('tags',{tags})}>Применить теги</button><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk(trash?'restore':'trash')}>{trash?'Восстановить':'В корзину'}</button></div>}
      {loading?<p role="status">Загрузка списка…</p>:!items.length?<p>Нет файлов по выбранным условиям.</p>:<div className="ws-media-table"><table><thead><tr>{editable&&<th><input aria-label="Выбрать страницу" type="checkbox" checked={pageSelected} disabled={pending} onChange={e=>setSelected(previous=>{const value=new Set(previous);items.forEach(i=>e.target.checked?value.size<500&&value.add(i.id):value.delete(i.id));return value;})} /></th>}<th>Файл</th><th>Папка</th><th>Теги</th><th>Координаты</th></tr></thead><tbody>{items.map(item=><tr key={item.id}>{editable&&<td><input type="checkbox" aria-label={`Выбрать ${item.name}`} checked={selected.has(item.id)} disabled={pending||(!selected.has(item.id)&&selected.size>=500)} onChange={()=>setSelected(previous=>{const value=new Set(previous);value.has(item.id)?value.delete(item.id):value.add(item.id);return value;})} /></td>}<td><button className="bp-text-button" disabled={trash} onClick={()=>setPreview(String(item.id))}>{item.name}</button></td><td>{folders.find(f=>f.id===item.folder_id)?.name||'Без папки'}</td><td>{item.tags||'—'}</td><td>{item.latitude!=null&&item.longitude!=null?`${item.latitude.toFixed(5)}, ${item.longitude.toFixed(5)}`:'—'}</td></tr>)}</tbody></table></div>}
      <div className="ws-pagination"><span>Страница {cursor.length}</span><button className="ws-secondary" disabled={cursor.length===1||loading} onClick={()=>setCursor(v=>v.slice(0,-1))}>Назад</button><button className="ws-secondary" disabled={!next||loading} onClick={()=>next&&setCursor(v=>[...v,next])}>Далее</button></div></>:<div className="ws-media-map"><MapContainer center={[43,47]} zoom={5} style={{height:'100%',width:'100%'}} preferCanvas><CatalogBounds query={query} onError={setError} /><PanoLayer endpoint="/api/media/markers" query={query} onMarkerClick={m=>{if(!trash)setPreview(m.id);}} /></MapContainer><span className="ws-media-map-note">Без внешней подложки · точки загружаются по области карты</span></div>}
    {preview&&!trash&&<section className="ws-media-preview" aria-label="Просмотр панорамы"><button className="ws-secondary ws-media-preview-close" onClick={()=>setPreview(null)}>Закрыть просмотр</button><PanoramaViewer markerId={preview} isExpanded={false} /></section>}
  </div>;
}
