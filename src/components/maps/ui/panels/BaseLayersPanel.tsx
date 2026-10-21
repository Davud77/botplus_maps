import React, { useEffect, useState } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import { useSettings } from '../../../../utils/mapSettings';
export const BaseLayersPanel: React.FC<{onClose:()=>void}> = ({onClose}) => {
  const {data,load}=useSettings(); const {baseLayerId}=useMapStore(); const [error,setError]=useState('');
  useEffect(()=>{load().catch(e=>setError(e.message));},[load]);
  return <BasePanel title="Подложки и координаты" onClose={onClose}>{error && <p role="alert">{error}</p>}<p className="bp-muted">Собственные источники добавляются в «Данные и настройки → Подложки».</p>{data?.basemaps.map(item=><button className={`bp-basemap ${baseLayerId===item.id?'selected':''}`} key={item.id} onClick={()=>useMapStore.setState({baseLayerId:item.id,baseLayerUrl:item.url,baseDefinition:item})}><span>{item.name}</span><span>{baseLayerId===item.id?'●':'○'}</span></button>)}<h4>Система координат</h4><select aria-label="Система координат карты" value={useMapStore(s=>s.coordinateSystem)} onChange={e=>useMapStore.setState({coordinateSystem:e.target.value})}>{data?.coordinate_systems.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select><p className="bp-muted">СК для координат центра карты. Проекция веб-карты — Web Mercator.</p></BasePanel>;
};
