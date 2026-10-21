import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../utils/api';
import { workspaceRequest } from '../../utils/workspaceApi';
import { useSettings } from '../../utils/mapSettings';
interface Job { id:string;title:string;root_id:string;key:string;status:'queued'|'running'|'succeeded'|'failed'|'cancelled';attempts:number;progress:number;message:string;error:string|null;cancel_requested:boolean;result:{ortho_id:number;no_copy:boolean}|null; }
const names={queued:'В очереди',running:'Обработка',succeeded:'Готово',failed:'Ошибка',cancelled:'Отменено'};
export default function ImportJobs() {
  const [sources,setSources]=useState<{id:string;name:string}[]>([]);
  const [root,setRoot]=useState('');const [path,setPath]=useState('');const [title,setTitle]=useState('');
  const [mode,setMode]=useState('local');const [file,setFile]=useState<File|null>(null);
  const [override,setOverride]=useState(false);const [crs,setCrs]=useState('EPSG:4326');
  const [jobs,setJobs]=useState<Job[]>([]);const [offset,setOffset]=useState(0);
  const [notice,setNotice]=useState('');const [error,setError]=useState('');const [pollError,setPollError]=useState('');const [pending,setPending]=useState(false);
  const [uploadProgress,setUploadProgress]=useState(0);const [limit,setLimit]=useState(2*1024**3);
  const [events,setEvents]=useState<{id:string;lines:{at:string;message:string}[]}|null>(null);
  const {data,load}=useSettings();const busy=useRef(false);
  const refresh=useCallback(async()=>{
    if(busy.current)return;busy.current=true;
    try {setJobs((await workspaceRequest<{jobs:Job[]}>(`/imports/jobs?offset=${offset}`)).jobs);setPollError('');}catch(e){setPollError((e as Error).message);}finally{busy.current=false;}
  },[offset]);
  useEffect(()=>{load().catch(e=>setError(e.message));workspaceRequest<{sources:{id:string;name:string}[];upload_limit_bytes:number}>('/imports/sources').then(value=>{setSources(value.sources);setRoot(value.sources[0]?.id||'');setLimit(value.upload_limit_bytes);}).catch(e=>setError(e.message));},[load]);
  useEffect(()=>{refresh();const timer=setInterval(()=>{if(document.visibilityState==='visible')refresh();},5000);return()=>clearInterval(timer);},[refresh]);
  async function submit(event:React.FormEvent) {
    event.preventDefault();if(pending)return;setError('');setNotice('');setPending(true);
    try {
      let result:{job:Job};
      if(mode==='local')result=await workspaceRequest('/imports/jobs','POST',{root_id:root,key:path,title,source_crs_id:override?crs:null});
      else {
        if(!file)throw new Error('Выберите GeoTIFF.');if(file.size>limit)throw new Error('Файл больше лимита веб-загрузки. Подключите его с диска или NAS.');
        const body=new FormData();body.append('file',file);body.append('title',title);if(override)body.append('source_crs_id',crs);setUploadProgress(0);
        result=await new Promise<{job:Job}>((resolve,reject)=>{
          const xhr=new XMLHttpRequest();xhr.open('POST',`${API_BASE}/api/imports/uploads`);xhr.withCredentials=true;
          xhr.upload.onprogress=e=>{if(e.lengthComputable)setUploadProgress(Math.round(e.loaded/e.total*100));};
          xhr.onload=()=>{let value;try{value=JSON.parse(xhr.responseText);}catch{reject(new Error(`Ошибка загрузки (${xhr.status}).`));return;}if(xhr.status>=200 && xhr.status<300)resolve(value);else reject(new Error(value.message||'Не удалось загрузить файл.'));};
          xhr.onerror=()=>reject(new Error('Соединение прервано. Проверьте список заданий перед повтором загрузки.'));xhr.send(body);
        });
      }
      setNotice(`Задание ${result.job.id.slice(0,8)}: ${names[result.job.status]}. Можно закрыть страницу — обработка продолжится на сервере.`);
      setPath('');setTitle('');setOffset(0);await refresh();
    }catch(e){setError((e as Error).message);}finally{setPending(false);}
  }
  async function action(job:Job,command:string) {
    setError('');setPending(true);try{await workspaceRequest(`/imports/jobs/${job.id}/${command}`,'POST',{});await refresh();}catch(e){setError((e as Error).message);}finally{setPending(false);}
  }
  async function logs(job:Job) {
    try{const result=await workspaceRequest<{events:{at:string;message:string}[]}>(`/imports/jobs/${job.id}`);setEvents({id:job.id,lines:result.events});}catch(e){setError((e as Error).message);}
  }
  return <><section className="ws-card"><div className="ws-section-kicker">ЛОКАЛЬНЫЕ ДАННЫЕ</div><h2>Импорт геоданных</h2><p>Готовый COG подключается без копирования. Для обычного GeoTIFF сервер создаёт отдельный COG; исходный файл сохраняется.</p>
    <div className="ws-tabs" aria-label="Способ импорта"><button type="button" className={mode==='local'?'active':''} onClick={()=>setMode('local')}>С диска / NAS</button><button type="button" className={mode==='upload'?'active':''} onClick={()=>setMode('upload')}>Загрузить файл</button></div>
    {(error||pollError) && <div className="ws-notice ws-error" role="alert">{error||pollError}</div>}{notice && <div className="ws-notice" role="status">{notice}</div>}
    <form className="ws-form-narrow" onSubmit={submit}>
      {mode==='local' ? <><label htmlFor="import-source">Подключённая папка</label><select id="import-source" value={root} onChange={e=>setRoot(e.target.value)} disabled={pending||!sources.length}>{!sources.length && <option value="">Нет подключённых папок</option>}{sources.map(source=><option key={source.id} value={source.id}>{source.name}</option>)}</select>
        {!sources.length && <p className="bp-muted">Папки ещё не подключены. Попросите администратора добавить источник данных в конфигурации сервера.</p>}
        <label htmlFor="import-path">Путь внутри папки</label><input id="import-path" placeholder="survey/orthophoto.tif" required value={path} onChange={e=>setPath(e.target.value)} disabled={pending} /><small>Файл должен быть доступен серверу. Браузер и CLI не передают его содержимое.</small></> : <><label htmlFor="import-file">GeoTIFF</label><input id="import-file" type="file" accept=".tif,.tiff" required disabled={pending} onChange={e=>setFile(e.target.files?.[0]||null)} /><small>До {(limit/1024**3).toFixed(1)} ГБ. Для больших файлов используйте диск/NAS. Возобновление веб-загрузки пока не поддерживается.</small>{pending && <progress max={100} value={uploadProgress} aria-label="Прогресс загрузки файла" />}</>}
      <label htmlFor="import-title">Название слоя</label><input id="import-title" maxLength={120} placeholder="По умолчанию — имя файла" value={title} onChange={e=>setTitle(e.target.value)} disabled={pending} />
      <label className="bp-inline-check"><input type="checkbox" checked={override} onChange={e=>setOverride(e.target.checked)} disabled={pending} />У исходника отсутствует или неверно указана СК</label>
      {override && <><label htmlFor="import-crs">Исходная система координат</label><select id="import-crs" value={crs} onChange={e=>setCrs(e.target.value)}>{data?.coordinate_systems.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select><small>Это исходная привязка, а не СК показываемых координат. Будет создан отдельный COG; оригинал останется без изменений.</small></>}
      <button className="ws-primary" disabled={pending||(mode==='local'&&!root)}>{pending?'Отправляем…':'Начать импорт'}</button>
    </form>
  </section><section className="ws-card"><div className="ws-page-heading"><div><h2>Задания импорта</h2><p>Задания сохраняются после перезапуска приложения. Если обработчик остановится, незавершённая работа будет автоматически запущена повторно.</p></div><button className="ws-secondary" onClick={refresh}>Обновить</button></div>
    {!jobs.length && <p>На этой странице пока нет заданий.</p>}
    {jobs.map(job=><article className="bp-import-job" key={job.id}><div className="bp-import-job-heading"><strong>{job.title}</strong><span className={`ws-badge ${job.status==='succeeded'?'green':''}`}>{names[job.status]}</span></div><small>{job.root_id==='__uploads'?'Веб-загрузка':`${job.root_id} / ${job.key}`} · попыток: {job.attempts}</small><progress max={100} value={job.progress} aria-label={`Прогресс ${job.title}`} /><p>{job.message}{job.cancel_requested&&job.status==='running'?' · Отмена запрошена':''}</p>{job.error && <p role="alert" className="bp-import-error">{job.error}</p>}{job.result && <p>{job.result.no_copy?'Подключён без копирования':'Подготовлен отдельный COG'} · слой №{job.result.ortho_id}. Добавьте его через «Ортофотопланы» в редакторе карты.</p>}<div className="ws-actions"><button className="ws-secondary" onClick={()=>logs(job)}>Журнал</button>{['queued','running'].includes(job.status)&&<button className="ws-secondary" disabled={pending||job.cancel_requested} onClick={()=>action(job,'cancel')}>Отменить</button>}{['failed','cancelled'].includes(job.status)&&<button className="ws-secondary" disabled={pending} onClick={()=>action(job,'retry')}>Повторить</button>}</div>{events?.id===job.id && <ol className="bp-job-events">{events.lines.map((line,index)=><li key={index}><small>{new Date(line.at).toLocaleString('ru-RU')}</small>{line.message}</li>)}</ol>}</article>)}
    <div className="ws-pagination"><span>Страница {offset/50+1}</span><button className="ws-secondary" disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Назад</button><button className="ws-secondary" disabled={jobs.length<50} onClick={()=>setOffset(offset+50)}>Далее</button></div>
  </section></>;
}
