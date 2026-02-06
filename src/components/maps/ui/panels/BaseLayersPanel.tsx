import React from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';

interface LayerOption {
  name: string;
  url: string;
  image: string;
}

const LAYERS: LayerOption[] = [
  { name: "OSM", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", image: "/images/OSM.png" },
  { name: "Google Satellite", url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", image: "/images/GoogleSatellite.png" },
  { name: "Google Hybrid", url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", image: "/images/GoogleHybrid.png" },
  { name: "Google Maps", url: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", image: "/images/GoogleMaps.png" },
  { name: "CartoDB Dark", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png", image: "/images/CartoDBDarkMatter.png" }
];

export const BaseLayersPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { baseLayerUrl, setBaseLayer } = useMapStore();

  return (
    <BasePanel title="Слои карты" onClose={onClose}>
      <div className="layers-grid">
        {LAYERS.map((layer) => (
          <div 
            key={layer.name} 
            className={`layer-card ${baseLayerUrl === layer.url ? 'active' : ''}`}
            onClick={() => setBaseLayer(layer.url)}
          >
            <div className="image-wrapper">
              <img src={layer.image} alt={layer.name} onError={(e) => (e.currentTarget.src = 'https://placehold.co/100x60?text=Map')} />
              <div className="layer-name">{layer.name}</div>
            </div>
            {baseLayerUrl === layer.url && <div className="active-indicator">✓</div>}
          </div>
        ))}
      </div>

      <style>{`
        .layers-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .layer-card { 
          position: relative; cursor: pointer; border-radius: 6px; overflow: hidden; 
          border: 2px solid transparent; transition: all 0.2s;
        }
        .layer-card.active { border-color: #2196F3; }
        .image-wrapper { position: relative; height: 80px; }
        .image-wrapper img { width: 100%; height: 100%; object-fit: cover; }
        .layer-name {
          position: absolute; bottom: 0; left: 0; right: 0;
          background: rgba(0,0,0,0.6); color: white; font-size: 11px;
          padding: 4px; text-align: center;
        }
        .active-indicator {
          position: absolute; top: 5px; right: 5px; background: #2196F3;
          color: white; width: 18px; height: 18px; border-radius: 50%;
          font-size: 12px; display: flex; align-items: center; justify-content: center;
        }
      `}</style>
    </BasePanel>
  );
};