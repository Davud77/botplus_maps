import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, ZoomControl, useMapEvents } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Search from './Search';

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

const ContextMenu = ({ contextMenu, handleCopyCoordinates }) => {
  if (!contextMenu.visible) return null;

  return (
    <div
      className="context-menu"
      style={{
        top: `${contextMenu.y}px`,
        left: `${contextMenu.x}px`
      }}
    >
      <button onClick={handleCopyCoordinates}>Скопировать координаты</button>
    </div>
  );
};

const MapEventHandlers = ({ setView }) => {
  useMapEvents({
    contextmenu: (event) => {
      const { latlng, containerPoint } = event;
      setView(latlng.lat, latlng.lng, containerPoint.x, containerPoint.y);
    },
    click: () => {
      setView(null, null, null, null);
    }
  });
  return null;
};

const MapContainerCanvas = ({ selectedMarker, handleMarkerClick, isVisible }) => {
  const [markers, setMarkers] = useState([]);
  const [mapCenter, setMapCenter] = useState([55, 47]);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });

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

  const handleRightClick = (lat, lng, x, y) => {
    setContextMenu({
      visible: true,
      x: x,
      y: y,
      lat: lat,
      lng: lng
    });
  };

  const handleCopyCoordinates = () => {
    const coords = `${contextMenu.lat.toFixed(6)}, ${contextMenu.lng.toFixed(6)}`;
    navigator.clipboard.writeText(coords)
      .catch(err => console.error('Failed to copy coordinates:', err));
    setContextMenu({ ...contextMenu, visible: false });
  };

  const hideContextMenu = () => {
    setContextMenu({ ...contextMenu, visible: false });
  };

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

  return (
    <div style={{ height: isVisible ? '50vh' : '100vh', width: '100%', position: 'relative' }}>
      <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false} ref={mapRef} maxZoom={22}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={22} />
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
        <MapEventHandlers setView={handleRightClick} />
      </MapContainer>
      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={handleCopyCoordinates} />
      <Search handleSearch={handleSearch} />
    </div>
  );
};

export default MapContainerCanvas;
