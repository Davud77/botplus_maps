import { LayerPane } from '../maps/layers/LayerPane';
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE } from '../../utils/api';
import { MapConfig, LayerPresentation, legacyBasemap, workspaceRequest } from '../../utils/workspaceApi';
import VectorTileLayer from '../maps/layers/VectorTileLayer';
import './Workspace.css';
interface PublishedMap { title: string; description: string; config: MapConfig; }
export default function PublicMapPage() {
  const { slug } = useParams();
  const [map, setMap] = useState<PublishedMap | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    setMap(null); setError('');
    workspaceRequest<{ map: PublishedMap }>(`/public/maps/${slug}`).then(result => { if (live) setMap(result.map); }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [slug]);
  const overlays=useMemo(()=>{
    if(!map)return [];
    const keys=[...map.config.vector_layers.map((_,index)=>`vector:${index}`),...map.config.orthophoto_ids.map(id=>`ortho:${id}`),...(map.config.base_layer!=='none'?['basemap']:[])];
    const saved=map.config.layer_settings||[];
    return [...saved,...keys.filter(key=>!saved.some(item=>item.key===key)).map((key):LayerPresentation=>({key}))].map(item=>{
      const index=+item.key.slice(item.key.indexOf(':')+1);
      const styles=map.config.vector_layers[index] ? {[map.config.vector_layers[index].tableName]:{type:'single' as const,style:{color:'#20664e',weight:2,fillOpacity:0.25,...item.style,fillColor:item.style?.color||'#20664e',fill:true}}} : {};
      return {...item,index,styles};
    });
  },[map]);
  const base=map?.config.base_layer_definition;
  const baseUrl=base?.url ?? legacyBasemap(map?.config.base_layer||'none');
  return <main className="ws-shell ws-map-editor"><header className="ws-map-topbar"><Link className="ws-brand" to="/"><span>B+</span>BotPlus Maps</Link><div className="ws-map-name"><strong>{map?.title || 'Публичная карта'}</strong><small>{map?.description || 'Опубликовано владельцем · просмотр по ссылке'}</small></div><span className="ws-badge green">Только просмотр</span></header>
    {error ? <div className="ws-empty" role="alert"><h1>Карта недоступна</h1><p>{error}</p></div> : map ? <div className="ws-public-canvas"><MapContainer center={map.config.view.center} zoom={map.config.view.zoom} maxZoom={23} preferCanvas style={{ height: '100%', width: '100%' }}>
      {overlays.filter(layer=>layer.visible!==false).map((layer,order)=><LayerPane key={layer.key} name={`public-${layer.key}`} style={{zIndex:400+overlays.length-order,opacity:layer.opacity??1}}>{layer.key==='basemap' ? (baseUrl && <TileLayer url={baseUrl} maxZoom={24} maxNativeZoom={base?.max_zoom??22} tms={base?.scheme==='tms'} attribution={base?.attribution||''} />) : layer.key.startsWith('ortho:') ? <TileLayer url={`${API_BASE}/api/public/maps/${slug}/orthophotos/${layer.index}/tiles/{z}/{x}/{y}.png`} maxZoom={23} /> : <VectorTileLayer pane={`public-${layer.key}`} coordinateUrl={`/public/maps/${slug}/coordinates/${layer.key}`} url={`${API_BASE}/api/public/maps/${slug}/vectors/${layer.index}/tiles/{z}/{x}/{y}.pbf`} active styleConfigs={layer.styles} />}</LayerPane>)}
    </MapContainer></div> : <div className="ws-empty" role="status">Загрузка публикации…</div>}
  </main>;
}
