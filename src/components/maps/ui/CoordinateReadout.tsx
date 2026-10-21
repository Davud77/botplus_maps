import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { useMapStore } from '../hooks/useMapStore';
import { workspaceRequest } from '../../../utils/workspaceApi';
export function CoordinateReadout() {
  const map=useMap(); const code=useMapStore(s=>s.coordinateSystem); const [text,setText]=useState('');
  useEffect(()=>{let live=true; let sequence=0; const update=async()=>{const current=++sequence; const center=map.getCenter().wrap();try{const result=await workspaceRequest<{x:number;y:number;unit:string;name:string}>(`/settings/coordinates?crs=${encodeURIComponent(code)}&lat=${center.lat}&lng=${center.lng}`);if(live && current===sequence)setText(`${result.name} · X ${result.x.toFixed(result.unit==='°'?6:2)} · Y ${result.y.toFixed(result.unit==='°'?6:2)} ${result.unit}`);}catch(e){if(live && current===sequence)setText((e as Error).message);}};update();map.on('moveend',update);return()=>{live=false;map.off('moveend',update);};},[map,code]);
  return <div className="bp-coordinate-readout" aria-label="Координаты центра карты">{text}</div>;
}
