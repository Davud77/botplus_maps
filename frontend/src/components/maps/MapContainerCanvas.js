import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, ZoomControl, ImageOverlay, useMapEvents } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import Search from '../maps/Search';
import BaseLayer from '../maps/baseLayer/baseLayer';
import { ContextMenu, MapEventHandlers, handleRightClick, handleCopyCoordinates } from '../maps/ContextMenu';
import { defaultIcon, activeIcon } from '../icons';
import PanoLayer from '../maps/panoLayer/panoLayer';
import OrthoLayer from '../maps/orthoLayer/orthoLayer';

const MapContainerCanvas = ({ selectedMarker, handleMarkerClick, isVisible }) => {
  const [markers, setMarkers] = useState([]);
  const [mapCenter, setMapCenter] = useState([55, 47]);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });
  const [baseLayer, setBaseLayer] = useState('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png');
  const [showPanoLayer, setShowPanoLayer] = useState(false);
  const [showOrthoLayer, setShowOrthoLayer] = useState(false);
  const [orthoImages, setOrthoImages] = useState([]);
  const [isSearchExpanded, setIsSearchExpanded] = useState(false);

  const mapRef = useRef(null);

  const rightClickHandler = handleRightClick(setContextMenu);
  const copyCoordinatesHandler = handleCopyCoordinates(contextMenu, setContextMenu);

  // Обработчик поиска координат
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

  // Обработчик изменения базового слоя карты
  const handleLayerChange = (layerUrl) => {
    setBaseLayer(layerUrl);
  };

  // Переключатель слоя панорам
  const togglePanoLayer = (newMarkers) => {
    setShowPanoLayer(!showPanoLayer);
    setMarkers(newMarkers);
  };

  // Переключатель слоя ортофотопланов
  const toggleOrthoLayer = (newOrthoImages) => {
    setShowOrthoLayer(!showOrthoLayer);
    setOrthoImages(newOrthoImages);
  };

  // Обработчик кликов на карту
  const MapClickHandler = () => {
    useMapEvents({
      click: () => {
        if (isSearchExpanded) {
          setIsSearchExpanded(false);
        }
      }
    });
    return null;
  };

  return (
    <div style={{ height: isVisible ? '50vh' : '100vh', width: '100%', position: 'relative' }}>
      <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false} ref={mapRef} maxZoom={22}>
        <TileLayer url={baseLayer} maxZoom={22} />
        {showPanoLayer && (
          <MarkerClusterGroup disableClusteringAtZoom={18} maxClusterRadius={50}>
            {markers.map((marker, index) => (
              <Marker
                position={[marker.lat, marker.lng]}
                key={`${marker.lat}-${marker.lng}-${index}`}
                icon={selectedMarker && selectedMarker.lat === marker.lat && selectedMarker.lng === marker.lng ? activeIcon : defaultIcon}
                eventHandlers={{ click: () => handleMarkerClick(marker) }}
              />
            ))}
          </MarkerClusterGroup>
        )}
        {showOrthoLayer && orthoImages.map((image, index) => (
          <ImageOverlay
            key={index}
            bounds={[
              [image.bounds.south, image.bounds.west],
              [image.bounds.north, image.bounds.east]
            ]}
            url={image.url}
          />
        ))}
        <ZoomControl position="bottomright" />
        <MapClickHandler />
        <MapEventHandlers setView={rightClickHandler} setContextMenu={setContextMenu} />
      </MapContainer>
      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={copyCoordinatesHandler} />
      <Search handleSearch={handleSearch} isExpanded={isSearchExpanded} setIsExpanded={setIsSearchExpanded} />
      <BaseLayer handleLayerChange={handleLayerChange} />
      <PanoLayer togglePanoLayer={togglePanoLayer} />
      <OrthoLayer toggleOrthoLayer={toggleOrthoLayer} />
    </div>
  );
};

export default MapContainerCanvas;
