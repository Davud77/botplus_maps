import React, { useState } from 'react';
import L from 'leaflet';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
export const OrthoPanel: React.FC<{onClose:()=>void;map:L.Map|null}> = ({onClose,map}) => {
  const {orthoImages,selectedOrthoIds,isLoadingOrtho,toggleOrtho,fitToBounds}=useMapStore(); const [query,setQuery]=useState('');
  return <BasePanel title="Ортофотопланы" onClose={onClose}><p className="bp-muted">Добавьте ортофотоплан в карту. Браузер загружает только видимые тайлы.</p><input className="bp-search" aria-label="Поиск ортофотопланов" placeholder="Найти ортофотоплан…" value={query} onChange={e=>setQuery(e.target.value)} />{isLoadingOrtho && <p>Загрузка…</p>}{!isLoadingOrtho && !orthoImages.length && <p>Ортофотопланы ещё не загружены.</p>}{orthoImages.filter(o=>o.filename.toLowerCase().includes(query.toLowerCase())).map(o=><div className="bp-catalog-row" key={o.id}><div><button className="bp-layer-focus" title="Показать область слоя" disabled={!o.wgs84_bounds || !map} onClick={()=>fitToBounds(o.id)}><strong>{o.filename}</strong></button></div><button className="bp-add-button" disabled={selectedOrthoIds.includes(o.id)} aria-label={`Добавить ${o.filename}`} onClick={()=>{if(!useMapStore.getState().selectedOrthoIds.includes(o.id))toggleOrtho(o.id);}}>{selectedOrthoIds.includes(o.id)?'✓':'+'}</button></div>)}</BasePanel>;
};
