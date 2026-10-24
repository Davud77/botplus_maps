import React, { useState } from 'react';
import L from 'leaflet';
import {useSettings} from '../../../../utils/mapSettings';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
export const OrthoPanel: React.FC<{onClose:()=>void;map:L.Map|null}> = ({onClose,map}) => {
  const catalog=useSettings(s=>s.data);
  const {orthoImages,selectedOrthoIds,isLoadingOrtho,toggleOrtho,fitToBounds}=useMapStore(); const [query,setQuery]=useState('');
  return <BasePanel title="Ортофотопланы" onClose={onClose}><p className="bp-muted">Добавьте ортофотоплан в карту. Браузер загружает только видимые тайлы.</p><input className="bp-search" aria-label="Поиск ортофотопланов" placeholder="Найти ортофотоплан…" value={query} onChange={e=>setQuery(e.target.value)} />{isLoadingOrtho && <p>Загрузка…</p>}{!isLoadingOrtho && !orthoImages.length && <p>Ортофотопланы ещё не загружены.</p>}{orthoImages.filter(o=>(o.display_name||o.filename).toLowerCase().includes(query.toLowerCase())).map(o=><div className="bp-catalog-row" key={o.id}><div><button className="bp-layer-focus" title="Показать область слоя" disabled={!o.wgs84_bounds || !map} onClick={()=>fitToBounds(o.id)}><strong>{o.display_name||o.filename}</strong></button><small>{o.display_ready?'Подготовлен для быстрого показа':'Для карты не подготовлен'}{o.crs?` · Проекция: ${catalog?.coordinate_systems.find(c=>c.id===o.crs)?.name||o.crs_name||o.crs}`:''}</small></div><button className="bp-add-button" disabled={selectedOrthoIds.includes(o.id)||!o.wgs84_bounds} aria-label={`Добавить ${o.display_name||o.filename}`} onClick={()=>{if(!useMapStore.getState().selectedOrthoIds.includes(o.id))toggleOrtho(o.id);}}>{selectedOrthoIds.includes(o.id)?'✓':'+'}</button></div>)}</BasePanel>;
};
