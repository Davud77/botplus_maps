import React, { useEffect, useState } from 'react';
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
export function LayerSettings({layer,name,kind,onBack}: {layer:LayerPresentation;name:string;kind:'vector'|'ortho'|'panoramas'|'basemap';onBack:()=>void}) {
  const {data,load}=useSettings();const update=useLayerStyleStore(s=>s.update);
  const [error,setError]=useState('');
  const code=layer.coordinate_system || (kind==='basemap'?'EPSG:3857':'EPSG:4326');
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
    {kind==='basemap' && <p className="bp-muted">Источник подложки можно заменить в панели «Подложки».</p>}
    <p className="bp-muted">Изменения применяются сразу. Сохраните карту через «Настройки карты».</p>
  </div>;
}
