import React, { useState } from 'react';

interface BaseLayerProps {
  handleLayerChange: (layerUrl: string) => void;
}

const BaseLayer: React.FC<BaseLayerProps> = ({ handleLayerChange }) => {
  const layers = [
    { name: "OSM", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", image: "/images/OSM.png" },
    { name: "Google Satellite", url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", image: "/images/GoogleSatellite.png" },
    { name: "Google Hybrid", url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", image: "/images/GoogleHybrid.png" },
    { name: "Google Maps", url: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", image: "/images/GoogleMaps.png" },
    { name: "ESRI Satellite", url: "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", image: "/images/ESRISatellite.png" },
    { name: "CartoDB Positron", url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", image: "/images/CartoDBPositron.png" },
    { name: "CartoDB Dark Matter", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png", image: "/images/CartoDBDarkMatter.png" }
  ];

  const [layersVisible, setLayersVisible] = useState(false);

  return (
    <div>
      <button className="layers-button" onClick={() => setLayersVisible(!layersVisible)}>
        <img 
          src="/images/svg/layers-icon.svg" 
          alt="Слои карты"
          width="30"
          height="30"
        />
      </button>
      <div className={`layers-menu ${layersVisible ? 'visible' : ''}`}>
        <div className="layers-header">
          <h3 className="layers-title">Выберите слой</h3>
          <button className="close-button" onClick={() => setLayersVisible(false)}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="24px"
              viewBox="0 0 24 24"
              width="24px"
              fill="#fff"
            >
              <path d="M0 0h24v24H0V0z" fill="none" />
              <path d="M18.3 5.71a1 1 0 0 0-1.41 0L12 10.59 7.11 5.71a1 1 0 1 0-1.41 1.41L10.59 12l-4.89 4.88a1 1 0 1 0 1.41 1.41L12 13.41l4.88 4.89a1 1 0 0 0 1.41-1.41L13.41 12l4.89-4.88a1 1 0 0 0 0-1.41z" />
            </svg>
          </button>
        </div>
        <div className="layers-grid">
          {layers.map((layer) => (
            <div className="layer-item" key={layer.name} onClick={() => { handleLayerChange(layer.url); setLayersVisible(false); }}>
              <div className="layer-image-container">
                <img src={layer.image} alt={layer.name} className="layer-image" />
                <div className="layer-gradient"></div>
                <span className="layer-name">{layer.name}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default BaseLayer;
