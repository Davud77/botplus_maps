import React, { useState, useEffect } from 'react';
import { MapContainer, LayersControl, ZoomControl, Marker, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import TMSLayers from './TMSLayers';
import PanoramaViewer from './PanoramaViewer';
import MarkerInfo from './MarkerInfo';
import Header from './Header';

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

const MapPage = () => {
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [mapCenter] = useState([42.9764, 47.5024]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    fetch('https://api.botplus.ru/panoramas')
      .then(response => response.json())
      .then(data => {
        const newMarkers = data.map(item => ({
          lat: item.latitude,
          lng: item.longitude,
          imageUrl: item.filename,
          tags: item.tags
        }));
        setMarkers(newMarkers);
      })
      .catch(error => {
        console.error('Error fetching panoramas:', error);
        alert('Не удалось загрузить данные о панорамах.');
      });
  }, []);

  const handleMarkerClick = (marker) => {
    setSelectedMarker(marker);
    setIsVisible(true); // Показать элемент при клике на маркер
  };

  const toggleHeight = () => {
    setIsExpanded(!isExpanded);
  };

  const closeInfo = () => {
    setIsVisible(false);
  };

  return (
    <div>
      <Header />  
      <MapContainer center={mapCenter} zoom={6} style={{ height: '100vh', width: '100%' }} zoomControl={false}>
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
      {selectedMarker && isVisible && (
        <div className="selected-marker-info" style={{ height: isExpanded ? '100%' : '50%' }}>
          
          <PanoramaViewer imageUrl={selectedMarker.imageUrl} height={isExpanded ? '89vh' : '50vh'} />
          <MarkerInfo tags={selectedMarker.tags} latitude={selectedMarker.lat} longitude={selectedMarker.lng} />
          <div className="visible_control">
            <button className="button button_control" onClick={toggleHeight} >
              <img src={isExpanded ? "/images/collapse.png" : "/images/expand.png"} alt={isExpanded ? "Свернуть" : "Развернуть"} />
            </button>
            <button className="button button_control" onClick={closeInfo}>
              <img src="/images/close.png" alt="Закрыть" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MapPage;
