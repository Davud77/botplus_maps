import React,{useState,useEffect,useCallback,useMemo,useRef} from 'react';
import {useMap,CircleMarker,Polyline} from 'react-leaflet';
import debounce from 'lodash/debounce';
import L,{LatLngBounds} from 'leaflet';
import {PanoramaSettings,defaultPanoramaSettings,usePanoramaRuntime} from '../../../utils/panoramaSettings';
import {workspaceRequest} from '../../../utils/workspaceApi';
interface MarkerType {id:string;lat:number;lng:number;count:number;cluster?:boolean;}
interface Props {coverageEndpoint?:string;publicView?:boolean;endpoint?:string;query?:string;pane?:string;selectedMarker?:string|null;onMarkerClick?:(marker:MarkerType)=>void;togglePanoLayer?:(markers:MarkerType[])=>void;options?:Partial<PanoramaSettings>;}
type Lines=[number,number][][];
export default function PanoLayer({endpoint='/api/panoramas',query='',pane='overlayPane',selectedMarker=null,onMarkerClick,togglePanoLayer,options,coverageEndpoint='/api/media/coverage',publicView=false}:Props){
 const settings=useMemo(()=>({...defaultPanoramaSettings,...options}),[options]);
 const {mode,pointZoom,detail}=settings;
 const map=useMap();const renderer=useMemo(()=>L.canvas({pane,padding:.3}),[pane]);
 const [coverage,setCoverage]=useState<Lines>([]);const [markers,setMarkers]=useState<MarkerType[]>([]);
 const revision=usePanoramaRuntime(s=>s.revision);const jobId=usePanoramaRuntime(s=>s.jobId);
 const generation=useRef(0);const controller=useRef<AbortController|null>(null);
 const loaded=useRef<{bounds:LatLngBounds;zoom:number;key:string}|null>(null);
 const lineCache=useRef<{bounds:LatLngBounds;key:string;lines:Lines}|null>(null);
 const cancel=useCallback(()=>{generation.current++;controller.current?.abort();},[]);
 useEffect(()=>{
  if(!jobId||publicView)return;
  let live=true;let timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{
   try{const {job}=await workspaceRequest<{job:{status:string;progress:number;message:string}}>(`/imports/jobs/${jobId}`);if(!live)return;
    const state=usePanoramaRuntime.getState();
    if(['succeeded','failed','cancelled'].includes(job.status)){state.finish(job.status==='succeeded'?'Покрытие перестроено.':job.message);return;}
    state.progress(`${job.message} · ${job.progress}%`);timer=setTimeout(poll,2000);
   }catch(e){if(live)usePanoramaRuntime.getState().finish((e as Error).message);}
  };poll();return()=>{live=false;clearTimeout(timer);};
 },[jobId,publicView]);
 const fetchView=useCallback(async(bounds:LatLngBounds,zoom:number)=>{
  const key=`${endpoint}:${coverageEndpoint}?${query}:${mode}:${pointZoom}:${detail}:${revision}`;
  if(loaded.current?.key===key&&loaded.current.zoom===zoom&&loaded.current.bounds.contains(bounds))return;
  const sequence=++generation.current;controller.current?.abort();controller.current=new AbortController();
  if(zoom<3){loaded.current=null;setMarkers([]);setCoverage([]);return;}
  const area=bounds.pad(.3);const points=mode==='points'||zoom>=pointZoom;
  const params=new URLSearchParams(query);params.set('west',String(area.getWest()));params.set('east',String(area.getEast()));params.set('south',String(area.getSouth()));params.set('north',String(area.getNorth()));params.set('zoom',String(Math.floor(zoom)));
  try{
   if(points){
    params.set('limit','1000');params.set('points','1');
    const response=await fetch(`${endpoint}?${params}`,{signal:controller.current.signal});if(!response.ok)throw new Error(`Панорамы: ${response.status}`);
    const data=await response.json();if(sequence!==generation.current)return;
    const rows:MarkerType[]=Array.isArray(data)?data.filter(p=>!p.cluster&&p.count===1&&typeof p.lat==='number'&&typeof p.lng==='number').map(p=>({...p,id:String(p.id)})):[];
    setMarkers(rows);setCoverage([]);togglePanoLayer?.(rows);
   }else{
    const cached=lineCache.current;
    if(cached?.key===key&&cached.bounds.contains(bounds)){
     setCoverage(cached.lines);setMarkers([]);
    }else{
     params.set('lines','1');params.set('detail',detail);
     const response=await fetch(`${coverageEndpoint}?${params}`,{signal:controller.current.signal});if(!response.ok)throw new Error(`Покрытие: ${response.status}`);
     const geometry=await response.json();if(sequence!==generation.current)return;
     const source=geometry.type==='LineString'?[geometry.coordinates]:geometry.type==='MultiLineString'?geometry.coordinates:[];
     const lines:Lines=source.map((line:number[][])=>line.map(([lng,lat])=>[lat,lng] as [number,number]));
     lineCache.current={bounds:area,key,lines};setCoverage(lines);setMarkers([]);
    }
   }
   loaded.current={bounds:area,zoom,key};
  }catch(e){if((e as Error).name!=='AbortError')console.error('Панорамы:',e);}
 },[endpoint,coverageEndpoint,query,mode,pointZoom,detail,revision,togglePanoLayer]);
 const delayedFetch=useMemo(()=>debounce((bounds:LatLngBounds,zoom:number)=>fetchView(bounds,zoom),160),[fetchView]);
 useEffect(()=>{
  const start=()=>{delayedFetch.cancel();cancel();};
  const end=()=>delayedFetch(map.getBounds(),map.getZoom());
  map.on('zoomstart',start);map.on('moveend',end);map.on('zoomend',end);end();
  return()=>{map.off('zoomstart',start);map.off('moveend',end);map.off('zoomend',end);delayedFetch.cancel();cancel();loaded.current=null;};
 },[map,delayedFetch,cancel]);
 const openPoints=(event:L.LeafletMouseEvent)=>{
  L.DomEvent.stopPropagation(event);
  map.flyTo(event.latlng,Math.min(map.getMaxZoom(),Math.max(18,pointZoom)),{animate:true,duration:.85,easeLinearity:.25});
 };
 return <>
  {coverage.length>0&&<>
   {settings.outlineWidth>0&&<Polyline pane={pane} renderer={renderer} positions={coverage} pathOptions={{color:settings.outlineColor,weight:settings.weight+settings.outlineWidth*2,opacity:.95,lineCap:'round',lineJoin:'round'}} eventHandlers={{click:openPoints}}/>}
   <Polyline pane={pane} renderer={renderer} positions={coverage} pathOptions={{color:settings.color,weight:settings.weight,opacity:1,lineCap:'round',lineJoin:'round'}} eventHandlers={{click:openPoints}}/>
  </>}
  {markers.map(marker=><CircleMarker key={marker.id} pane={pane} renderer={renderer} center={[marker.lat,marker.lng]} radius={settings.pointRadius} pathOptions={{fillColor:selectedMarker===marker.id?'#ff3b30':settings.pointColor,color:settings.outlineColor,weight:1.5,fillOpacity:1}} eventHandlers={{click:event=>{L.DomEvent.stopPropagation(event);onMarkerClick?.(marker);}}}/>)}
 </>;
}
