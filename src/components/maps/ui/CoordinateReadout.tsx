import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import {useSettings} from '../../../utils/mapSettings';
import { useMapStore } from '../hooks/useMapStore';
import { workspaceRequest } from '../../../utils/workspaceApi';
export function CoordinateReadout() {
  const map=useMap(); const code=useMapStore(s=>s.coordinateSystem); const [text,setText]=useState(''); const [zoom,setZoom]=useState(()=>map.getZoom());
  const projectionName=useSettings(s=>s.data?.coordinate_systems.find(c=>c.id===code)?.name);
  useEffect(()=>{let live=true; let sequence=0; const update=async()=>{const current=++sequence; setZoom(map.getZoom()); const center=map.getCenter().wrap();try{const result=await workspaceRequest<{x:number;y:number;unit:string;name:string}>(`/settings/coordinates?crs=${encodeURIComponent(code)}&lat=${center.lat}&lng=${center.lng}`);if(live && current===sequence)setText(`${result.name} · X ${result.x.toFixed(result.unit==='°'?6:2)} · Y ${result.y.toFixed(result.unit==='°'?6:2)} ${result.unit}`);}catch(e){if(live && current===sequence)setText((e as Error).message);}};update();const updateZoom=()=>setZoom(map.getZoom());map.on('moveend',update);map.on('zoomend',updateZoom);return()=>{live=false;map.off('moveend',update);map.off('zoomend',updateZoom);};},[map,code,projectionName]);
  return <div className="bp-coordinate-readout" aria-label="Координаты центра карты">{text}<span className="bp-coordinate-zoom">· Z: {zoom.toFixed(1).replace(/\.0$/,'')}</span></div>;
}
