import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE } from '../../utils/api';
import { workspaceRequest } from '../../utils/workspaceApi';
import SourcePicker from './SourcePicker';
import MediaImport from './MediaImport';
const types=[{id:'raster',name:'Ортофотопланы',description:'GeoTIFF / COG'},{id:'panoramas',name:'Панорамы',description:'JPEG / WebP с GPS'}];
export default function ImportJobs() {
 const params=new URLSearchParams(window.location.search);const [kind,setKind]=useState(params.get('type')==='panoramas'?'panoramas':'raster');const [mode,setMode]=useState(params.get('mode')==='local'?'local':'upload');
 const [sources,setSources]=useState<{id:string;name:string}[]>([]);const [selection,setSelection]=useState<{root:string;key:string}|null>(null);const [files,setFiles]=useState<File[]>([]);const [title,setTitle]=useState('');const [error,setError]=useState('');const [notice,setNotice]=useState('');const [pending,setPending]=useState(false);const [limit,setLimit]=useState(2*1024**3);const [progress,setProgress]=useState(0);
 useEffect(()=>{workspaceRequest<{sources:{id:string;name:string}[];upload_limit_bytes:number}>('/imports/sources').then(r=>{setSources(r.sources);setLimit(r.upload_limit_bytes);}).catch(e=>setError(e.message));},[]);
 const choose=(root:string,key:string)=>setSelection(root?{root,key}:null);
 async function submit(e:React.FormEvent){e.preventDefault();setError('');setNotice('');setPending(true);try{
  const results:{ortho_id:number;projection?:string;warning?:string;existing?:boolean}[]=[];
  if(mode==='local'){
   if(!selection)throw new Error('Выберите файл в хранилище.');
   const r=await workspaceRequest<{result:typeof results[number]}>('/imports/register','POST',{root_id:selection.root,key:selection.key,title});results.push(r.result);
  }else{
   if(!files.length)throw new Error('Выберите GeoTIFF.');if(files.length>100)throw new Error('До 100 файлов за один выбор.');
   for(const file of files){if(file.size>limit)throw new Error(`${file.name}: файл больше веб-лимита. Выберите его на NAS.`);const body=new FormData();body.append('file',file);body.append('title',title||file.name);setProgress(0);
    const value=await new Promise<{result:typeof results[number]}>((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',`${API_BASE}/api/imports/files`);xhr.withCredentials=true;xhr.upload.onprogress=e=>{if(e.lengthComputable)setProgress(Math.round(e.loaded/e.total*100));};xhr.onload=()=>{try{const r=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300)resolve(r);else reject(new Error(r.message||'Ошибка импорта.'));}catch(e){reject(e);}};xhr.onerror=()=>reject(new Error('Передача прервана. Проверьте каталог перед повтором.'));xhr.send(body);});results.push(value.result);
   }
  }
  setNotice(results.map(r=>`ОФП №${r.ortho_id}${r.projection?` · ${r.projection}`:''}: ${r.existing?'уже в каталоге':'импортирован без обработки'}. ${r.warning||''}`).join('\n'));
 }catch(e){setError((e as Error).message);}finally{setPending(false);}}
 return <section className="ws-card"><div className="ws-section-kicker">ЛОКАЛЬНЫЕ ДАННЫЕ</div><h2>Импорт геоданных</h2><p>Загрузите оригиналы или подключите их с NAS. Импорт не меняет файлы и не запускает обработку. Подготовка COG и журналы доступны отдельно в «Заданиях».</p>
 <div className="ws-import-types" aria-label="Тип данных">{types.map(t=><button type="button" key={t.id} aria-pressed={kind===t.id} disabled={pending} onClick={()=>{setKind(t.id);setSelection(null);setError('');setNotice('');}}><strong>{t.name}</strong><small>{t.description}</small></button>)}</div>
 <div className="ws-tabs" aria-label="Способ импорта"><button disabled={pending} className={mode==='upload'?'active':''} onClick={()=>setMode('upload')}>Загрузить файл</button><button disabled={pending} className={mode==='local'?'active':''} onClick={()=>setMode('local')}>С диска / NAS</button></div>
 {mode==='local'&&<SourcePicker sources={sources} kind={kind} onSelect={choose}/>}
 {selection&&mode==='local'&&<p className="ws-notice">Выбрано: {selection.root} / {selection.key}</p>}
 {error&&<p role="alert" className="ws-notice ws-error">{error}</p>}{notice&&<p role="status" className="ws-notice ws-import-result">{notice}</p>}
 {kind==='panoramas'?<MediaImport mode={mode} sources={sources} selection={selection}/>:<form className="ws-form-narrow" onSubmit={submit}>{mode==='upload'&&<><label htmlFor="import-file">GeoTIFF / COG</label><input id="import-file" type="file" accept=".tif,.tiff" multiple disabled={pending} onChange={e=>setFiles(Array.from(e.target.files||[]))}/><small>До {(limit/1024**3).toFixed(1)} ГБ на запрос. Для крупных файлов используйте NAS. Файлы сохраняются последовательно, без преобразования.</small>{pending&&<progress max="100" value={progress} aria-label="Передача файла"/>}</>}
 <label htmlFor="import-title">Название в каталоге</label><input id="import-title" value={title} maxLength={120} placeholder="По умолчанию — имя файла" disabled={pending} onChange={e=>setTitle(e.target.value)}/><button className="ws-primary" disabled={pending||(mode==='local'&&!selection)}>{pending?'Сохраняем…':'Импортировать'}</button></form>}
 <p className="bp-muted">Неизвестная проекция получит имя unknown_1, unknown_2 и далее. Привязка не угадывается, оригинал сохраняется.</p><Link to="/profile?section=tasks">Перейти к заданиям и журналам →</Link></section>;
}
