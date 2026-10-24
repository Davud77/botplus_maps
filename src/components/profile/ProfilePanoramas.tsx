import React, {useCallback,useEffect,useMemo,useState} from 'react';
import {Link} from 'react-router-dom';
import {createPortal} from 'react-dom';
import {MapContainer,TileLayer,useMap} from 'react-leaflet';
import {useAuth} from '../../hooks/useAuth';
import {baseLayers,workspaceRequest} from '../../utils/workspaceApi';
import PanoLayer from '../maps/layers/PanoLayer';
import PanoramaViewer from '../maps/ui/viewers/PanoramaViewer';
interface Item {id:number;name:string;folder_id:number|null;tags:string;latitude:number;longitude:number;media_type:string|null;width?:number;height?:number;timestamp?:string;deleted_at?:string|null;}
interface BulkResult {affected:number;active_total:number;trash_total:number;}
interface Folder {id:number;name:string;}
const fields=[{id:'preview',name:'Просмотр'},{id:'name',name:'Название'},{id:'folder',name:'Папка'},{id:'tags',name:'Теги'},{id:'coordinates',name:'Координаты'},{id:'type',name:'Тип'},{id:'size',name:'Размер изображения'},{id:'date',name:'Дата съёмки'},{id:'id',name:'ID'}] as const;
type Field=typeof fields[number]['id'];
interface Column {id:Field;visible:boolean;}
const defaults=():Column[]=>fields.map(f=>({id:f.id,visible:['preview','name','tags','coordinates'].includes(f.id)}));
function readColumns(key:string):Column[]{
 try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(!Array.isArray(saved))return defaults();const result:Column[]=[];for(const c of saved)if(fields.some(f=>f.id===c.id)&&typeof c.visible==='boolean'&&!result.some(f=>f.id===c.id))result.push(c);return [...result,...defaults().filter(c=>!result.some(f=>f.id===c.id))];}catch{return defaults();}
}
function CatalogBounds({query,onError}:{query:string;onError:(text:string)=>void}){
 const map=useMap();useEffect(()=>{let live=true;workspaceRequest<{bounds:{west:number;south:number;east:number;north:number}|null}>(`/media/bounds?${query}`).then(({bounds:b})=>{if(live&&b)map.fitBounds([[b.south,b.west],[b.north,b.east]],{padding:[24,24],maxZoom:18});}).catch(e=>{if(live)onError(e.message);});return()=>{live=false;};},[map,query,onError]);return null;
}
export default function ProfilePanoramas(){
 const {user}=useAuth();const editable=user?.role!=='viewer';
 const [total,setTotal]=useState<number|null>(null);const [items,setItems]=useState<Item[]>([]);const [folders,setFolders]=useState<Folder[]>([]);
 const [trash,setTrash]=useState(false);const [view,setView]=useState('list');const [selected,setSelected]=useState<Set<number>>(new Set());
 const [cursor,setCursor]=useState<number[]>([0]);const [next,setNext]=useState<number|null>(null);
 const [tags,setTags]=useState('');const [error,setError]=useState('');const [notice,setNotice]=useState('');const [loading,setLoading]=useState(false);const [pending,setPending]=useState(false);const [revision,setRevision]=useState(0);const [preview,setPreview]=useState<string|null>(null);
 const storageKey=`botplus_panorama_columns_${user?.id||'local'}`;
 const [columns,setColumns]=useState<Column[]>(()=>readColumns(storageKey));const [settings,setSettings]=useState(false);
 useEffect(()=>{setColumns(readColumns(storageKey));},[storageKey]);
 function changeColumns(value:Column[]){setColumns(value);try{localStorage.setItem(storageKey,JSON.stringify(value));}catch{}}
 function moveColumn(index:number,delta:number){const value=[...columns];[value[index],value[index+delta]]=[value[index+delta],value[index]];changeColumns(value);}
 const query=useMemo(()=>new URLSearchParams({trash:trash?'1':'0'}).toString(),[trash]);const after=cursor[cursor.length-1];
 function openTrash(value:boolean){setTrash(value);setTotal(null);setItems([]);setNext(null);setCursor([0]);setSelected(new Set());setPreview(null);setNotice('');setError('');setSettings(false);setView('list');}
 useEffect(()=>{let live=true;setLoading(true);workspaceRequest<{items:Item[];next_cursor:number|null;total:number}>(`/media/catalog?${query}&limit=200&after=${after}`).then(value=>{if(live){setItems(value.items);setNext(value.next_cursor);setTotal(value.total);}}).catch(e=>{if(live)setError(e.message);}).finally(()=>{if(live)setLoading(false);});return()=>{live=false;};},[query,after,revision]);
 const loadFolders=useCallback(async()=>setFolders((await workspaceRequest<{folders:Folder[]}>('/media/folders')).folders),[]);
 useEffect(()=>{loadFolders().catch(e=>setError(e.message));},[loadFolders]);
 async function run<T>(action:()=>Promise<T>,message:string|((result:T)=>string)){setPending(true);setError('');setNotice('');try{const result=await action();setItems([]);setNotice(typeof message==='function'?message(result):message);setSelected(new Set());setCursor([0]);setRevision(r=>r+1);}catch(e){setError((e as Error).message);}finally{setPending(false);}}
 const bulk=(action:string,extra={})=>run(()=>workspaceRequest<BulkResult>('/media/bulk','POST',{ids:[...selected],action,...extra}),r=>{
  setTotal(trash?r.trash_total:r.active_total);
  const count=r.affected.toLocaleString('ru-RU');
  return action==='trash'?`Удалено в корзину: ${count}. Осталось панорам: ${r.active_total.toLocaleString('ru-RU')}.`:action==='restore'?`Восстановлено: ${count}.`:action==='purge'?`Удалено окончательно: ${count}.`:'Изменения сохранены.';
 });
 function purge(){if(window.confirm(`Удалить выбранные панорамы (${selected.size}) окончательно? Восстановить их из корзины будет нельзя.`))bulk('purge');}
 function empty(){if(window.confirm('Очистить всю корзину? Восстановить удалённые записи будет нельзя.'))run(()=>workspaceRequest('/media/trash/empty','POST',{}),'Корзина очищена.');}
 const pageSelected=items.length>0&&items.every(i=>selected.has(i.id));const visible=columns.filter(c=>c.visible);
 function cell(item:Item,id:Field):React.ReactNode{
  switch(id){
   case 'preview':return trash?'—':<button className="ws-secondary ws-media-open" aria-label={`Открыть ${item.name}`} title={item.name} onClick={()=>setPreview(String(item.id))}>↗</button>;
   case 'name':return item.name;case 'folder':return folders.find(f=>f.id===item.folder_id)?.name||'—';case 'tags':return item.tags||'—';
   case 'coordinates':return item.latitude!=null&&item.longitude!=null?`${item.latitude.toFixed(5)}, ${item.longitude.toFixed(5)}`:'—';
   case 'type':return item.media_type==='panorama'?'Панорама':item.media_type==='photo'?'Фото':'—';
   case 'size':return item.width&&item.height?`${item.width} × ${item.height}`:'—';
   case 'date':return item.timestamp?new Date(item.timestamp).toLocaleString('ru-RU'):'—';case 'id':return item.id;
  }
 }
 return <div className="ws-media-catalog">
  <div className="ws-media-toolbar"><nav aria-label="Каталог панорам"><a href="#panoramas" aria-current={!trash?'page':undefined} onClick={e=>{e.preventDefault();if(!pending)openTrash(false);}}>Панорамы</a> · <a href="#trash" aria-current={trash?'page':undefined} onClick={e=>{e.preventDefault();if(!pending)openTrash(true);}}>Корзина</a></nav>
   {!trash&&<><div className="ws-tabs" aria-label="Вид каталога"><button className={view==='list'?'active':''} onClick={()=>setView('list')}>Список</button><button className={view==='map'?'active':''} onClick={()=>setView('map')}>Карта</button></div><button className="ws-secondary" aria-expanded={settings} onClick={()=>setSettings(v=>!v)}>Настройка полей</button>{editable&&<Link className="ws-primary" to="/profile?section=imports&type=panoramas&mode=upload">Импортировать</Link>}</>}
  </div>
  {error&&<p className="ws-notice ws-error" role="alert">{error}</p>}{notice&&<p className="ws-notice" role="status">{notice}</p>}
  {settings&&!trash&&<section className="ws-column-settings" aria-label="Настройка полей"><p>Выберите видимые поля и задайте порядок стрелками.</p>{columns.map((c,i)=><div className="ws-column-setting" key={c.id}><label><input type="checkbox" checked={c.visible} disabled={c.visible&&visible.length===1} onChange={e=>changeColumns(columns.map(v=>v.id===c.id?{...v,visible:e.target.checked}:v))}/>{fields.find(f=>f.id===c.id)?.name}</label><button className="ws-secondary" aria-label={`Выше: ${fields.find(f=>f.id===c.id)?.name}`} disabled={!i} onClick={()=>moveColumn(i,-1)}>↑</button><button className="ws-secondary" aria-label={`Ниже: ${fields.find(f=>f.id===c.id)?.name}`} disabled={i===columns.length-1} onClick={()=>moveColumn(i,1)}>↓</button></div>)}</section>}
  {view==='list'||trash?<>
   {editable&&<div className="ws-media-bulk" role="toolbar" aria-label={trash?'Действия корзины':'Действия панорам'}><strong>Выбрано: {selected.size}</strong>{trash?<><button className="ws-secondary" disabled={!selected.size||pending} onClick={purge}>Удалить окончательно</button><button className="ws-secondary" disabled={!items.length||pending} onClick={empty}>Очистить</button><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk('restore')}>Восстановить</button></>:<><input aria-label="Теги выбранных файлов" placeholder="Теги выбранных…" maxLength={2000} value={tags} onChange={e=>setTags(e.target.value)}/><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk('tags',{tags})}>Применить теги</button><button className="ws-secondary" disabled={!selected.size||pending} onClick={()=>bulk('trash')}>Удалить</button></>}</div>}
   <p className="ws-media-count">{trash?'В корзине':'Панорам в каталоге'}: <strong>{total==null?'…':total.toLocaleString('ru-RU')}</strong></p>
   {loading?<p role="status">Загрузка списка…</p>:!items.length?<p>{trash?'Корзина пуста.':'Нет панорам.'}</p>:<div className="ws-media-table"><table><thead><tr>{editable&&<th><input aria-label="Выбрать страницу" type="checkbox" checked={pageSelected} disabled={pending} onChange={e=>setSelected(previous=>{const value=new Set(previous);items.forEach(i=>e.target.checked?value.size<500&&value.add(i.id):value.delete(i.id));return value;})}/></th>}{visible.map(c=><th key={c.id}>{fields.find(f=>f.id===c.id)?.name}</th>)}</tr></thead><tbody>{items.map(item=><tr key={item.id}>{editable&&<td><input type="checkbox" aria-label={`Выбрать ${item.name}`} checked={selected.has(item.id)} disabled={pending||(!selected.has(item.id)&&selected.size>=500)} onChange={()=>setSelected(previous=>{const value=new Set(previous);value.has(item.id)?value.delete(item.id):value.add(item.id);return value;})}/></td>}{visible.map(c=><td key={c.id} data-label={fields.find(f=>f.id===c.id)?.name} data-field={c.id}>{cell(item,c.id)}</td>)}</tr>)}</tbody></table></div>}
   <div className="ws-pagination"><span>Страница {cursor.length}</span><button className="ws-secondary" disabled={cursor.length===1||loading||pending} onClick={()=>{setItems([]);setCursor(v=>v.slice(0,-1));}}>Назад</button><button className="ws-secondary" disabled={!next||loading||pending} onClick={()=>next&&setCursor(v=>[...v,next])}>Далее</button></div>
  </>:<div className="ws-media-map"><MapContainer center={[43,47]} zoom={5} maxZoom={23} zoomAnimation wheelPxPerZoomLevel={100} wheelDebounceTime={60} style={{height:'100%',width:'100%'}} preferCanvas><TileLayer url={baseLayers.osm} attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' maxNativeZoom={19} maxZoom={23}/><CatalogBounds query={query} onError={setError}/><PanoLayer endpoint="/api/media/markers" query={query} onMarkerClick={m=>setPreview(m.id)}/></MapContainer></div>}
  {preview&&!trash&&createPortal(<section className="ws-media-preview" aria-label="Просмотр панорамы"><button className="ws-secondary ws-media-preview-close" aria-label="Закрыть просмотр" title="Закрыть просмотр" onClick={()=>setPreview(null)}>×</button><PanoramaViewer markerId={preview} isExpanded={false}/></section>,document.body)}
 </div>;
}
