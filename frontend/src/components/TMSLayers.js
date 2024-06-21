import React, { useState } from 'react';

const TMSLayers = ({ handleLayerChange }) => {
  const layers = [
    { name: "OSM", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" },
    { name: "Google Satellite", url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" },
    { name: "Google Hybrid", url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}" },
    { name: "Google Maps", url: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}" },
    { name: "ESRI Satellite", url: "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" }
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
      {layersVisible && (
        <div className="layers-menu">
          <h3>Выберите слой</h3>
          <div className="layers-grid">
            {layers.map((layer) => (
              <button key={layer.name} onClick={() => { handleLayerChange(layer.url); setLayersVisible(false); }}>
                {layer.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TMSLayers;
