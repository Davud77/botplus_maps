import React from 'react';
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

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

const MapContainerCanvas = ({ markers, selectedMarker, handleMarkerClick, mapCenter, isVisible }) => {
  return (
    <div style={{ height: isVisible ? '50vh' : '100vh', width: '100%' }}>
      <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MarkerClusterGroup
          disableClusteringAtZoom={18} // Отключить кластеризацию на уровне приближения 10 и выше
          maxClusterRadius={50} // Радиус кластеризации в пикселях
        >
          {markers.map((marker, index) => (
            <Marker
              position={[marker.lat, marker.lng]}
              key={`${marker.lat}-${marker.lng}-${index}`}
              icon={selectedMarker && selectedMarker.lat === marker.lat && selectedMarker.lng === marker.lng ? activeIcon : defaultIcon}
              eventHandlers={{ click: () => handleMarkerClick(marker) }}
            />
          ))}
        </MarkerClusterGroup>
        <ZoomControl position="bottomright" />
      </MapContainer>
    </div>
  );
};

export default MapContainerCanvas;
