import React, { useState, useEffect } from 'react';
import { MapContainer, LayersControl, ZoomControl, Marker, TileLayer } from 'react-leaflet';
import { Link } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Marzipano from 'marzipano';
import data from './uploads/list.json';
import TMSLayers from './TMSLayers';
import PanoramaViewer from './PanoramaViewer'; // Предполагается, что вынесен в отдельный файл
import MarkerInfo from './MarkerInfo'; // Предполагается, что вынесен в отдельный файл
import Header from './Header'; // Импорт компонента Header

// Определение кастомных иконок для маркеров
const defaultIcon = new L.Icon({
  iconUrl: '/images/default-icon.png',
  iconSize: [25, 25],
  iconAnchor: [12, 12]
});

const activeIcon = new L.Icon({
  iconUrl: '/images/active-icon.png',
  iconSize: [30, 30],
  iconAnchor: [15, 15]
});

const MapPage = () => {
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [mapCenter, setMapCenter] = useState([42.9764, 47.5024]);

  useEffect(() => {
    const newMarkers = Object.keys(data).map(key => {
      const image = data[key];
      const [lat, lng] = image.metadata.gps;
      const imageUrl = `/uploads/${key}`;
      return { lat, lng, tags: image.tags.join(', '), imageUrl };
    });
    setMarkers(newMarkers);
  }, []);

  const handleMarkerClick = (marker) => {
    setSelectedMarker(marker);
  };


  
// Добавление Header в верхней части страницы
  return (
    <div>
      <Header />  
      <MapContainer center={mapCenter} zoom={10} style={{ height: '100vh', width: '100%' }} zoomControl={false}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="OpenStreetMap">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          </LayersControl.BaseLayer>
          <TMSLayers />
        </LayersControl>
        <ZoomControl position="bottomright" />
        {markers.map(marker => (
          <Marker
            position={[marker.lat, marker.lng]}
            key={`${marker.lat}-${marker.lng}`}
            icon={selectedMarker && selectedMarker.lat === marker.lat && selectedMarker.lng === marker.lng ? activeIcon : defaultIcon}
            eventHandlers={{ click: () => handleMarkerClick(marker) }}
          />
        ))}
      </MapContainer>
      {selectedMarker && (
        <div className="selected-marker-info">
          <PanoramaViewer imageUrl={selectedMarker.imageUrl} />
          <MarkerInfo tags={selectedMarker.tags} latitude={selectedMarker.lat} longitude={selectedMarker.lng} />
        </div>
      )}
    </div>
  );
};

export default MapPage;
