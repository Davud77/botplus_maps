import React, {useCallback,useEffect,useState} from 'react';
import {useAuth} from '../../hooks/useAuth';
import {workspaceRequest} from '../../utils/workspaceApi';
import {OperationLog,readOperationLogs} from '../../utils/operationLogs';
interface Job {id:string;kind:'import'|'display'|'media';title:string;status:string;progress:number|null;message:string;error?:string;cancel_requested?:boolean;counts?:{processed:number;imported:number;skipped:number;failed:number};}
interface Logs {events:OperationLog[];services:OperationLog[];}
const names:Record<string,string>={queued:'В очереди',running:'Выполняется',succeeded:'Завершено',failed:'Ошибка',cancelled:'Отменено'};
const paths={import:'/imports/jobs',display:'/raster-display/jobs',media:'/media/imports'};
export default function TasksPanel(){
 const {user}=useAuth();
 const [tab,setTab]=useState<'jobs'|'logs'>('jobs');
 const [jobs,setJobs]=useState<Job[]>([]);
 const [error,setError]=useState('');
 const [pending,setPending]=useState(false);
 const [logs,setLogs]=useState<Logs>({events:[],services:[]});
 const [localLogs,setLocalLogs]=useState(readOperationLogs);
 const [service,setService]=useState('all');
 const [lines,setLines]=useState<{at:string;message:string}[]>([]);
 const refresh=useCallback(async()=>{try{setJobs((await workspaceRequest<{jobs:Job[]}>('/tasks')).jobs);}catch(e){setError((e as Error).message);}},[]);
 const refreshLogs=useCallback(async()=>{setLocalLogs(readOperationLogs());if(user?.role==='admin'){try{setLogs(await workspaceRequest<Logs>('/system/logs'));}catch(e){setError((e as Error).message);}}},[user?.role]);
 useEffect(()=>{refresh();const timer=setInterval(()=>{if(document.visibilityState==='visible')refresh();},5000);return()=>clearInterval(timer);},[refresh]);
 useEffect(()=>{if(tab!=='logs')return;refreshLogs();const timer=setInterval(refreshLogs,5000);window.addEventListener('operation-log',refreshLogs);return()=>{clearInterval(timer);window.removeEventListener('operation-log',refreshLogs);};},[tab,refreshLogs]);
 async function action(path:string){setPending(true);setError('');try{await workspaceRequest(path,'POST',{});await refresh();}catch(e){setError((e as Error).message);}finally{setPending(false);}}
 async function journal(job:Job){try{const r=await workspaceRequest<{events:{at:string;message:string}[]}>(`${paths[job.kind]}/${job.id}`);setLines(r.events);}catch(e){setError((e as Error).message);}}
 const allLogs=[...localLogs,...logs.events,...logs.services];
 const services=Array.from(new Set(allLogs.map(l=>l.service)));
 const groups=[{key:'running',title:'В работе'},{key:'queued',title:'В очереди'},{key:'finished',title:'Завершённые'}];
 return <section className="ws-card"><h2>Задания и логи</h2>
  <div className="ws-tabs ws-operation-tabs" role="tablist" aria-label="Операции и журналы">{(['jobs','logs'] as const).map(t=><button key={t} role="tab" aria-selected={tab===t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t==='jobs'?'Задания':'Логи'}</button>)}</div>
  {error&&<p role="alert" className="ws-notice ws-error">{error}</p>}
  {tab==='jobs'?<div role="tabpanel" aria-label="Задания">
   {!jobs.length&&<p>Заданий нет.</p>}
   {groups.map(group=>{const items=jobs.filter(j=>group.key==='finished'?!['running','queued'].includes(j.status):j.status===group.key);return items.length>0&&<div key={group.key}><h3>{group.title}</h3>{items.map(job=><article className="bp-import-job" key={`${job.kind}:${job.id}`}>
    <div className="bp-import-job-heading"><strong>{job.title}</strong><span className="ws-badge">{names[job.status]||job.status}</span></div>
    {job.status!=='queued'&&<><progress {...(job.progress===null?{}:{value:job.progress})} max={100} aria-label={`Прогресс ${job.title}`}/>{job.progress!==null&&<span> {job.progress}%</span>}</>}
    <p>{job.message}</p>{job.error&&<p role="alert">{job.error}</p>}
    {job.counts&&<small>Просмотрено: {job.counts.processed} · добавлено: {job.counts.imported} · пропущено: {job.counts.skipped} · ошибок: {job.counts.failed}</small>}
    <div className="ws-actions">
     {job.kind!=='media'&&<button className="ws-secondary" onClick={()=>journal(job)}>Журнал задания</button>}
     {['queued','running'].includes(job.status)?<button className="ws-secondary" disabled={pending||job.cancel_requested} onClick={()=>action(`${paths[job.kind]}/${job.id}/cancel`)}>Отменить</button>:<>
      {['failed','cancelled'].includes(job.status)&&<button className="ws-secondary" disabled={pending} onClick={()=>action(`${paths[job.kind]}/${job.id}/retry`)}>Повторить</button>}
      <button className="ws-primary" disabled={pending} onClick={()=>action(`/tasks/${job.kind}/${job.id}/done`)}>Готово</button>
     </>}
    </div>
   </article>)}</div>;})}
   {lines.length>0&&<ol className="bp-job-events">{lines.map((l,i)=><li key={i}><time>{new Date(l.at).toLocaleString('ru-RU')}</time> {l.message}</li>)}</ol>}
  </div>:<div role="tabpanel" aria-label="Логи"><select aria-label="Сервис журнала" value={service} onChange={e=>setService(e.target.value)}><option value="all">Все сервисы</option>{services.map(s=><option key={s}>{s}</option>)}</select>
   <div className="ws-system-logs" role="log" aria-label="Журналы системы">{allLogs.filter(l=>service==='all'||l.service===service).sort((a,b)=>(Date.parse(b.at)||0)-(Date.parse(a.at)||0)).map((l,i)=><div key={i}><time>{new Date(l.at).toLocaleString('ru-RU')}</time> <strong>{l.service}</strong> <span>{l.message}</span></div>)}</div>
  </div>}
 </section>;
}
