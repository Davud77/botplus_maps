import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE } from '../../utils/api';
import { MapConfig, baseLayers, workspaceRequest } from '../../utils/workspaceApi';
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
  const vectors = useMemo(() => map?.config.vector_layers.map((layer, index) => ({
    index, styles: { [layer.tableName]: { type: 'single' as const, style: { color: '#20664e', weight: 2, fillOpacity: 0.25 } } },
  })) || [], [map]);
  return <main className="ws-shell ws-map-editor"><header className="ws-map-topbar"><Link className="ws-brand" to="/"><span>B+</span>BotPlus Maps</Link><div className="ws-map-name"><strong>{map?.title || 'Публичная карта'}</strong><small>{map?.description || 'Опубликовано владельцем · просмотр по ссылке'}</small></div><span className="ws-badge green">Только просмотр</span></header>
    {error ? <div className="ws-empty" role="alert"><h1>Карта недоступна</h1><p>{error}</p></div> : map ? <div className="ws-public-canvas"><MapContainer center={map.config.view.center} zoom={map.config.view.zoom} maxZoom={23} preferCanvas style={{ height: '100%', width: '100%' }}>
      {baseLayers[map.config.base_layer] && <TileLayer url={baseLayers[map.config.base_layer]} maxZoom={23} attribution="© OpenStreetMap contributors · CARTO / provider" />}
      {map.config.orthophoto_ids.map(id => <TileLayer key={id} url={`${API_BASE}/api/public/maps/${slug}/orthophotos/${id}/tiles/{z}/{x}/{y}.png`} maxZoom={23} />)}
      {vectors.map(layer => <VectorTileLayer key={layer.index} url={`${API_BASE}/api/public/maps/${slug}/vectors/${layer.index}/tiles/{z}/{x}/{y}.pbf`} active styleConfigs={layer.styles} />)}
    </MapContainer></div> : <div className="ws-empty" role="status">Загрузка публикации…</div>}
  </main>;
}
