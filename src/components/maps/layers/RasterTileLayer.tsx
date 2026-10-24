import React, { useEffect, useMemo } from 'react';
import { TileLayerProps } from 'react-leaflet';
import TileLayer from './BatchedRasterTileLayer';
import { create } from 'zustand';
interface Load {label:string;loading:boolean;first?:number;total?:number;errors:number;loaded:number;}
const useLoads=create<{items:Record<string,Load>;put:(key:string,value:Load|null)=>void}>(set=>({items:{},put:(key,value)=>set(state=>{const items={...state.items};if(value)items[key]=value;else delete items[key];return {items};})}));

// A 512 px tile at URL zoom z-1 has exactly the same ground pixel size as
// four legacy 256 px tiles at z. Keep display detail; reduce dataset opens.
export default function RasterTileLayer({telemetryKey,label,...props}:TileLayerProps&{telemetryKey:string;label:string}) {
  const events=useMemo(()=>{
    let start=0;let first:number|undefined;let errors=0;let loaded=0;
    const put=(loading:boolean,total?:number)=>useLoads.getState().put(telemetryKey,{label,loading,first,total,errors,loaded});
    return {
      loading:()=>{start=performance.now();first=undefined;errors=0;loaded=0;put(true);},
      tileload:()=>{loaded+=1;if(first===undefined&&start){first=performance.now()-start;put(true);}},
      tileerror:()=>{errors+=1;},
      load:()=>{if(start)put(false,performance.now()-start);},
    };
  },[telemetryKey,label]);
  useEffect(()=>()=>useLoads.getState().put(telemetryKey,null),[telemetryKey]);
  return <TileLayer {...props} tileSize={512} zoomOffset={-1} minNativeZoom={1} updateWhenIdle updateWhenZooming={false} keepBuffer={1} eventHandlers={events}/>;
}
export function RasterLoadingStatus(){
  const items=useLoads(state=>state.items);
  return <section className="bp-raster-status" role="status" aria-label="Диагностика растров"><header><strong>Диагностика растров</strong><small>Тайлы 512 px · пакетная загрузка</small></header>{!Object.keys(items).length?<p>Ожидание загрузки растрового слоя…</p>:Object.entries(items).map(([key,item])=><div key={key}>
    <span>{item.label}</span><strong>{item.loading?'Загрузка…':item.errors?`Ошибок тайлов: ${item.errors}`:item.total===undefined?'Ожидание':`${(item.total/1000).toFixed(2)} с`}</strong>
    <small>Первый тайл: {item.first===undefined?'—':`${(item.first/1000).toFixed(2)} с`} · Тайлoв: {item.loaded} · Ошибок: {item.errors}</small>
  </div>)}</section>;
}
