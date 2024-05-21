// Файл: src/MapContainerCanvas.js
import React from 'react';
import { MapContainer, LayersControl, ZoomControl, Marker, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import TMSLayers from './TMSLayers';

// Определение кастомных иконок для маркеров
const defaultIcon = new L.Icon({
  iconUrl: '/images/default-icon.png',
  iconSize: [18, 18],
  iconAnchor: [9, 9]
});

const activeIcon = new L.Icon({
  iconUrl: '/images/active-icon.png',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

const MapContainerCanvas = ({ markers, selectedMarker, handleMarkerClick, mapCenter }) => {
  return (
    <MapContainer center={mapCenter} zoom={5} style={{ height: '100vh', width: '100%' }} zoomControl={false}>
      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="OpenStreetMap">
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        </LayersControl.BaseLayer>
        <TMSLayers />
      </LayersControl>
      <ZoomControl position="bottomright" />
      {markers.map((marker, index) => (
        <Marker
          position={[marker.lat, marker.lng]}
          key={`${marker.lat}-${marker.lng}-${index}`}
          icon={selectedMarker && selectedMarker.lat === marker.lat && selectedMarker.lng === marker.lng ? activeIcon : defaultIcon}
          eventHandlers={{ click: () => handleMarkerClick(marker) }}
        />
      ))}
    </MapContainer>
  );
};

export default MapContainerCanvas;
