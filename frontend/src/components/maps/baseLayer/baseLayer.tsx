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
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="30px"
          viewBox="0 0 24 24"
          width="30px"
          fill="#fff"
        >
          <path d="M0 0h24v24H0V0z" fill="none" />
          <path d="M4.43 12.42l5.29 3.15 1.62-.98-5.31-3.15zm6.38 3.79l5.29-3.15-1.62-.98-5.31 3.15zM12 10.8l5.29-3.15-1.62-.98-5.31 3.15z" opacity=".3" />
          <path d="M12 21.02l-8-4.8V7.79l8-4.8 8 4.8v8.43l-8 4.8zM6.62 16.62l5.38 3.23 5.38-3.23V10.8l-5.38 3.23-5.38-3.23v5.82zm11.16-7.68l-5.38-3.23-5.38 3.23 5.38 3.23 5.38-3.23z" />
        </svg>
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
