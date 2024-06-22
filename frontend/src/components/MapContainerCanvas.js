import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import Search from './Search';
import TMSLayers from './TMSLayers';
import { ContextMenu, MapEventHandlers, handleRightClick, handleCopyCoordinates } from './ContextMenu';
import { defaultIcon, activeIcon } from './icons';

const MapContainerCanvas = ({ selectedMarker, handleMarkerClick, isVisible }) => {
  const [markers, setMarkers] = useState([]);
  const [mapCenter, setMapCenter] = useState([55, 47]);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });
  const [baseLayer, setBaseLayer] = useState('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png');

  const mapRef = useRef(null);

  useEffect(() => {
    fetch('https://api.botplus.ru/panoramas')
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        const newMarkers = data.map(item => ({
          id: item.id,
          lat: item.latitude,
          lng: item.longitude
        }));
        setMarkers(newMarkers);
      })
      .catch(error => {
        console.error('Error fetching panoramas:', error);
        alert('Не удалось загрузить данные о панорамах.');
      });
  }, []);

  const rightClickHandler = handleRightClick(setContextMenu);
  const copyCoordinatesHandler = handleCopyCoordinates(contextMenu, setContextMenu);

  const handleSearch = (searchInput) => {
    const coords = searchInput.split(',').map(coord => parseFloat(coord.trim()));
    if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
      if (mapRef.current) {
        mapRef.current.setView(coords, 18);
      }
      setMapCenter(coords);
    } else {
      alert('Неверный формат координат. Используйте формат: 59.333189, 57.128906');
    }
  };

  const handleLayerChange = (layerUrl) => {
    setBaseLayer(layerUrl);
  };

  return (
    <div style={{ height: isVisible ? '50vh' : '100vh', width: '100%', position: 'relative' }}>
      <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false} ref={mapRef} maxZoom={22}>
        <TileLayer url={baseLayer} maxZoom={22} />
        <MarkerClusterGroup
          disableClusteringAtZoom={18}
          maxClusterRadius={50}
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
        <MapEventHandlers setView={rightClickHandler} />
      </MapContainer>
      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={copyCoordinatesHandler} />
      <Search handleSearch={handleSearch} />
      <TMSLayers handleLayerChange={handleLayerChange} />
    </div>
  );
};

export default MapContainerCanvas;
