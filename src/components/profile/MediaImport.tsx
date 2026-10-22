import React, { useState } from 'react';
import { API_BASE } from '../../utils/api';
import { workspaceRequest } from '../../utils/workspaceApi';
export default function MediaImport({mode,selection}:{mode:string;sources:{id:string;name:string}[];selection:{root:string;key:string}|null}) {
 const [files,setFiles]=useState<File[]>([]);const [only360,setOnly360]=useState(true);const [tags,setTags]=useState('');
 const [pending,setPending]=useState(false);const [progress,setProgress]=useState('');const [error,setError]=useState('');const [logs,setLogs]=useState<string[]>([]);
 async function submit(e:React.FormEvent) {e.preventDefault();setPending(true);setError('');setLogs([]);try{
  if(mode==='local'){if(!selection)throw new Error('Выберите папку или файл на NAS.');await workspaceRequest('/media/imports','POST',{root_id:selection.root,key:selection.key,only_360:only360});setProgress('Подключаем оригиналы без преобразования и копирования. Ход импорта отображается в «Заданиях».');}
  else {if(!files.length)throw new Error('Выберите JPEG или WebP.');if(files.length>100)throw new Error('Не более 100 файлов за один выбор. Для больших партий используйте NAS.');
   const lines:string[]=[];
   for(let index=0;index<files.length;index++){const file=files[index];if(file.size>128*1024**2){lines.push(`${file.name}: больше 128 МБ, используйте NAS.`);setLogs([...lines]);continue;}
    const body=new FormData();body.append('files',file);body.append('only_360',String(only360));body.append('tags',tags);
    const value=await new Promise<{successful_uploads:string[];failed_uploads:string[];skipped_files:string[]}>((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',`${API_BASE}/api/upload`);xhr.withCredentials=true;xhr.upload.onprogress=event=>setProgress(`Файл ${index+1} из ${files.length}: ${event.lengthComputable?Math.round(event.loaded/event.total*100):0}%`);xhr.onload=()=>{try{const result=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300)resolve(result);else reject(new Error(result.message||result.error||'Ошибка загрузки.'));}catch(e){reject(e);}};xhr.onerror=()=>reject(new Error('Соединение прервано. Проверьте каталог перед повторной отправкой.'));xhr.send(body);});
    lines.push(`${file.name}: ${value.failed_uploads.length?value.skipped_files.join('; '):'Загружен на NAS'}`);setLogs([...lines]);
   }setProgress('Передача завершена. Результат каждого файла указан ниже.');
  }
 }catch(e){setError((e as Error).message);}finally{setPending(false);}}
 return <><form className="ws-form-narrow" onSubmit={submit}>
 {mode==='upload'&&<><label htmlFor="media-files">JPEG / WebP</label><input id="media-files" type="file" accept=".jpg,.jpeg,.webp" multiple disabled={pending} onChange={e=>setFiles(Array.from(e.target.files||[]))}/><small>До 100 файлов за выбор, до 128 МБ на запрос. Передача требует открытой страницы. Файлы сохраняются без преобразования.</small><label htmlFor="media-tags">Теги</label><input id="media-tags" maxLength={2000} value={tags} disabled={pending} onChange={e=>setTags(e.target.value)}/></>}
 <label className="bp-inline-check"><input type="checkbox" checked={only360} disabled={pending} onChange={e=>setOnly360(e.target.checked)}/>Только панорамы 360°</label><small>Снимите флажок, чтобы также импортировать обычные фотографии с GPS.</small>
 <button className="ws-primary" disabled={pending||(mode==='local'&&!selection)}>{pending?'Импортируем…':'Начать импорт панорам'}</button></form>
 {error&&<p role="alert" className="ws-notice ws-error">{error}</p>}{progress&&<p role="status">{progress}</p>}{logs.length>0&&<ul className="ws-media-upload-log">{logs.map((line,i)=><li key={i}>{line}</li>)}</ul>}
 </>;
}
