import React, { useEffect, useMemo } from 'react';
import { TileLayer, TileLayerProps } from 'react-leaflet';
import { create } from 'zustand';
interface Load {label:string;loading:boolean;first?:number;total?:number;errors:number;}
const useLoads=create<{items:Record<string,Load>;put:(key:string,value:Load|null)=>void}>(set=>({items:{},put:(key,value)=>set(state=>{const items={...state.items};if(value)items[key]=value;else delete items[key];return {items};})}));

// A 512 px tile at URL zoom z-1 has exactly the same ground pixel size as
// four legacy 256 px tiles at z. Keep display detail; reduce dataset opens.
export default function RasterTileLayer({telemetryKey,label,...props}:TileLayerProps&{telemetryKey:string;label:string}) {
  const events=useMemo(()=>{
    let start=0;let first:number|undefined;let errors=0;
    const put=(loading:boolean,total?:number)=>useLoads.getState().put(telemetryKey,{label,loading,first,total,errors});
    return {
      loading:()=>{start=performance.now();first=undefined;errors=0;put(true);},
      tileload:()=>{if(first===undefined&&start){first=performance.now()-start;put(true);}},
      tileerror:()=>{errors+=1;},
      load:()=>{if(start)put(false,performance.now()-start);},
    };
  },[telemetryKey,label]);
  useEffect(()=>()=>useLoads.getState().put(telemetryKey,null),[telemetryKey]);
  return <TileLayer {...props} tileSize={512} zoomOffset={-1} minNativeZoom={1} updateWhenIdle updateWhenZooming={false} keepBuffer={1} eventHandlers={events}/>;
}
export function RasterLoadingStatus(){
  const items=useLoads(state=>state.items);
  if(!Object.keys(items).length)return null;
  return <div className="bp-raster-status" role="status" aria-label="Скорость загрузки ОФП">{Object.entries(items).map(([key,item])=><div key={key} title={`${item.label}${item.first===undefined?'':` · первый тайл ${(item.first/1000).toFixed(2)} с`}`}><span>{item.label}</span><strong>{item.loading?'Загрузка…':item.errors?`Ошибок тайлов: ${item.errors}`:item.total===undefined?'':`${(item.total/1000).toFixed(2)} с`}</strong></div>)}</div>;
}
