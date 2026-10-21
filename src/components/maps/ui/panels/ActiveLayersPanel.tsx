import React from 'react';
import { BasePanel } from './BasePanel';
import { useLayerStyleStore } from '../../hooks/useLayerStyleStore';
import { useMapStore } from '../../hooks/useMapStore';
import { useVectorStore } from '../../hooks/useVectorStore';
export function ActiveLayersPanel({onClose,onRemovePanos}: {onClose:()=>void;onRemovePanos:()=>void}) {
  const {layers,update,move}=useLayerStyleStore(); const {orthoImages}=useMapStore(); const {layerSources}=useVectorStore();
  return <BasePanel title="Слои на карте" onClose={onClose}><p className="bp-muted">Верхний слой отображается поверх остальных. Изменения сохраняются кнопкой «Сохранить карту».</p>{!layers.length && <p>Добавьте данные через «Векторные слои», «Ортофотопланы» или «Панорамы».</p>}{layers.map((item,index) => {
    const ortho=item.key.startsWith('ortho:'); const pano=item.key==='panoramas'; const id=+item.key.slice(6); const vectorId=item.key.slice(7);
    const name=ortho ? orthoImages.find(o=>o.id===id)?.filename || `Ортофото ${id}` : pano ? 'Панорамы' : layerSources[vectorId]?.tableName || vectorId;
    const style=item.style || {};
    return <section className="bp-layer-card" key={item.key}><div className="bp-layer-heading"><label><input type="checkbox" checked={item.visible!==false} onChange={e=>update(item.key,{visible:e.target.checked})} aria-label={`Видимость ${name}`} /><strong>{name}</strong></label><button title={`Удалить ${name} с карты`} className="bp-icon-button" onClick={()=> {if(ortho) useMapStore.setState(s=>({selectedOrthoIds:s.selectedOrthoIds.filter(v=>v!==id)})); else if(pano) onRemovePanos(); else useVectorStore.setState(s=>({activeVectorIds:new Set([...s.activeVectorIds].filter(v=>v!==vectorId))}));}}>×</button></div>
      <div className="bp-layer-meta"><small>{ortho ? 'Ортофотоплан' : pano ? 'Панорамы' : 'Векторный слой'}</small><button className="bp-icon-button" aria-label={`Поднять ${name}`} disabled={index===0} onClick={()=>move(item.key,-1)}>↑</button><button className="bp-icon-button" aria-label={`Опустить ${name}`} disabled={index===layers.length-1} onClick={()=>move(item.key,1)}>↓</button></div>
      <label className="bp-slider">Прозрачность <output>{Math.round((1-(item.opacity??1))*100)}%</output><input aria-label={`Прозрачность ${name}`} type="range" min="0" max="100" value={Math.round((1-(item.opacity??1))*100)} onChange={e=>update(item.key,{opacity:1-+e.target.value/100})} /></label>
      {!ortho && !pano && <details><summary>Стиль слоя</summary><div className="bp-style-grid"><label>Цвет<input aria-label={`Цвет ${name}`} type="color" value={style.color||'#20664e'} onChange={e=>update(item.key,{style:{...style,color:e.target.value}})} /></label><label>Толщина<input type="number" aria-label={`Толщина ${name}`} min="0" max="20" step="0.5" value={style.weight??2} onChange={e=>update(item.key,{style:{...style,weight:+e.target.value}})} /></label><label>Заливка<input type="range" aria-label={`Заливка ${name}`} min="0" max="1" step="0.05" value={style.fillOpacity??0.25} onChange={e=>update(item.key,{style:{...style,fillOpacity:+e.target.value}})} /></label><label>Радиус точек<input type="number" min="0" max="30" value={style.radius??5} onChange={e=>update(item.key,{style:{...style,radius:+e.target.value}})} /></label></div><button className="ws-secondary" onClick={()=>update(item.key,{style:{}})}>Стиль источника</button></details>}
    </section>;
  })}</BasePanel>;
}
