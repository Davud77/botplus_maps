import React, { useEffect, useState } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import { useSettings } from '../../../../utils/mapSettings';
export const BaseLayersPanel: React.FC<{onClose:()=>void}> = ({onClose}) => {
  const {data,load}=useSettings(); const {baseLayerId}=useMapStore(); const [error,setError]=useState('');
  useEffect(()=>{load().catch(e=>setError(e.message));},[load]);
  return <BasePanel title="Подложки" onClose={onClose}>{error && <p role="alert">{error}</p>}<p className="bp-muted">Собственные источники добавляются в «Данные и настройки → Подложки».</p>{data?.basemaps.map(item=><button className={`bp-basemap ${baseLayerId===item.id?'selected':''}`} key={item.id} onClick={()=>useMapStore.setState({baseLayerId:item.id,baseLayerUrl:item.url,baseDefinition:item})}><span>{item.name}</span><span>{baseLayerId===item.id?'●':'○'}</span></button>)}</BasePanel>;
};
