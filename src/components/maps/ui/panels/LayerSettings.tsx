import React, { useEffect, useState } from 'react';
import {defaultPanoramaSettings,PanoramaSettings,usePanoramaRuntime} from '../../../../utils/panoramaSettings';
import { LayerPresentation, workspaceRequest } from '../../../../utils/workspaceApi';
import { useSettings } from '../../../../utils/mapSettings';
import { useMapStore } from '../../hooks/useMapStore';
import { useLayerStyleStore } from '../../hooks/useLayerStyleStore';
function LayerCoordinates({code}: {code:string}) {
  const map=useMapStore(state=>state.mapInstance);
  const [text,setText]=useState('');
  useEffect(()=>{
    if(!map)return;
    let live=true;let sequence=0;
    const update=async()=>{
      const current=++sequence;const point=map.getCenter().wrap();
      try {
        const value=await workspaceRequest<{x:number;y:number;unit:string}>(`/settings/coordinates?crs=${encodeURIComponent(code)}&lat=${point.lat}&lng=${point.lng}`);
        if(live && current===sequence)setText(`X ${value.x.toFixed(value.unit==='°'?6:2)} · Y ${value.y.toFixed(value.unit==='°'?6:2)} ${value.unit}`);
      }catch(e){if(live && current===sequence)setText((e as Error).message);}
    };
    update();map.on('moveend',update);
    return()=>{live=false;map.off('moveend',update);};
  },[map,code]);
  return <output className="bp-layer-coordinates" aria-label="Координаты центра в СК слоя">{text || 'Пересчитываем координаты…'}</output>;
}
function PanoramaControls({layer}:{layer:LayerPresentation}) {
  const update=useLayerStyleStore(s=>s.update);
  const runtime=usePanoramaRuntime();
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const settings={...defaultPanoramaSettings,...layer.panorama};
  const change=<K extends keyof PanoramaSettings,>(key:K,value:PanoramaSettings[K])=>update(layer.key,{panorama:{...settings,[key]:value}});
  const rebuild=async()=>{
    setBusy(true);setError('');
    try{const {job}=await workspaceRequest<{job:{id:string}}>('/media/coverage/rebuild','POST',{});runtime.start(job.id);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  };
  return <>
    <h4>Отображение панорам</h4>
    <label>Режим<select aria-label="Режим панорам" value={settings.mode} onChange={e=>change('mode',e.target.value as PanoramaSettings['mode'])}><option value="auto">Линии → точки при приближении</option><option value="points">Только отдельные точки</option></select></label>
    <label>Точки начиная с Z<input aria-label="Уровень появления точек" type="number" min="18" max="22" value={settings.pointZoom} onChange={e=>change('pointZoom',Math.max(18,Math.min(22,+e.target.value)))} /></label>
    <label>Детализация линий<select aria-label="Детализация линий" value={settings.detail} onChange={e=>change('detail',e.target.value as PanoramaSettings['detail'])}><option value="fast">Быстрая · упрощение до 5 м</option><option value="balanced">Сбалансированная · до 2 м</option><option value="precise">Точная · до 0,2 м</option></select></label>
    <h4>Оформление</h4>
    <svg viewBox="0 0 220 42" width="100%" height="42" aria-label="Предпросмотр оформления панорам"><path d="M12 30 L70 12 L140 30 L208 12" fill="none" stroke={settings.outlineColor} strokeWidth={settings.weight+2*settings.outlineWidth} strokeLinejoin="round" strokeLinecap="round"/><path d="M12 30 L70 12 L140 30 L208 12" fill="none" stroke={settings.color} strokeWidth={settings.weight} strokeLinejoin="round" strokeLinecap="round"/><circle cx="140" cy="30" r={settings.pointRadius} fill={settings.pointColor} stroke={settings.outlineColor}/></svg>
    <div className="bp-style-grid">
      {(['color','outlineColor','pointColor'] as const).map((key,i)=><label key={key}>{['Цвет линии','Цвет обводки','Цвет точек'][i]}<input aria-label={['Цвет линии','Цвет обводки','Цвет точек'][i]} type="color" value={settings[key]} onChange={e=>change(key,e.target.value)}/></label>)}
      {(['weight','outlineWidth','pointRadius'] as const).map((key,i)=><label key={key}>{['Толщина линии','Ширина обводки','Радиус точек'][i]}<input aria-label={['Толщина линии','Ширина обводки','Радиус точек'][i]} type="number" min={[1,0,2][i]} max={[12,8,12][i]} value={settings[key]} onChange={e=>change(key,Math.max([1,0,2][i],Math.min([12,8,12][i],+e.target.value)))}/></label>)}
    </div>
    <button className="ws-secondary" onClick={()=>update(layer.key,{panorama:{...defaultPanoramaSettings}})}>Сбросить оформление</button>
    <h4>Перестроение покрытия</h4>
    <p className="bp-muted">Соседние панорамы соединяются в пределах одного трека, если расстояние не превышает 25 м. Разрывы сохраняются.</p>
    <button className="ws-secondary" onClick={runtime.refresh}>Обновить видимую область</button>
    <button className="ws-secondary" disabled={busy||!!runtime.jobId} onClick={rebuild}>Перестроить покрытие</button>
    <p className="bp-muted">Перестроение выполняется в фоне в общей очереди заданий. Исходные панорамы сохраняются.</p>
    {runtime.message&&<p role="status">{runtime.message}</p>}{error&&<p role="alert">{error}</p>}
  </>;
}
export function LayerSettings({layer,name,kind,onBack}: {layer:LayerPresentation;name:string;kind:'vector'|'ortho'|'panoramas'|'basemap';onBack:()=>void}) {
  const {data,load}=useSettings();const update=useLayerStyleStore(s=>s.update);
  const [error,setError]=useState('');
  const native=useMapStore(s=>s.orthoImages.find(o=>`ortho:${o.id}`===layer.key)?.crs);
  const code=layer.coordinate_system || (kind==='basemap'?'EPSG:3857':kind==='ortho'&&data?.coordinate_systems.some(c=>c.id===native)?native!:'EPSG:4326');
  const style=layer.style || {};
  useEffect(()=>{load().catch(e=>setError(e.message));},[load]);
  return <div className="bp-layer-settings">
    <button className="bp-text-button" onClick={onBack}>← Все слои</button>
    <h4 className="bp-layer-settings-name">{name}</h4>
    <label className="bp-slider">Прозрачность <output>{Math.round((1-(layer.opacity??1))*100)}%</output><input aria-label={`Прозрачность ${name}`} type="range" min="0" max="100" value={Math.round((1-(layer.opacity??1))*100)} onChange={e=>update(layer.key,{opacity:1-+e.target.value/100})} /></label>
    <label htmlFor="layer-coordinate-system">Система координат слоя</label>
    <select id="layer-coordinate-system" value={code} onChange={e=>update(layer.key,{coordinate_system:e.target.value})} disabled={!data}>{data ? data.coordinate_systems.map(item=><option key={item.id} value={item.id}>{item.name}</option>) : <option value={code}>{code}</option>}</select>
    <p className="bp-muted">СК для отображения координат. Исходный файл и его привязка сохраняются. Ниже — координаты центра карты.</p>
    {error && <p role="alert">{error}</p>}
    <LayerCoordinates code={code} />
    {kind==='vector' && <><h4>Стиль</h4><div className="bp-style-grid">
      <label>Цвет<input aria-label={`Цвет ${name}`} type="color" value={style.color||'#20664e'} onChange={e=>update(layer.key,{style:{...style,color:e.target.value}})} /></label>
      <label>Толщина<input type="number" aria-label={`Толщина ${name}`} min="0" max="20" step="0.5" value={style.weight??2} onChange={e=>update(layer.key,{style:{...style,weight:+e.target.value}})} /></label>
      <label>Заливка<input type="range" aria-label={`Заливка ${name}`} min="0" max="1" step="0.05" value={style.fillOpacity??0.25} onChange={e=>update(layer.key,{style:{...style,fillOpacity:+e.target.value}})} /></label>
      <label>Радиус точек<input type="number" aria-label={`Радиус точек ${name}`} min="0" max="30" value={style.radius??5} onChange={e=>update(layer.key,{style:{...style,radius:+e.target.value}})} /></label>
    </div><button className="ws-secondary" onClick={()=>update(layer.key,{style:{}})}>Стиль источника</button></>}
    {kind==='panoramas' && <PanoramaControls layer={layer}/> }
    {kind==='basemap' && <p className="bp-muted">Источник подложки можно заменить в панели «Подложки».</p>}
    <p className="bp-muted">Изменения применяются сразу. Сохраните карту через «Настройки карты».</p>
  </div>;
}
