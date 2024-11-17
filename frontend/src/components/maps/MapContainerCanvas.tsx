// src/components/maps/MapContainerCanvas.tsx

import React, { useState, useRef, useEffect } from 'react';
import {
  MapContainer,
  TileLayer,
  ZoomControl,
  ImageOverlay,
  useMapEvents,
  useMap,
} from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import Search from './Search';
import BaseLayer from './baseLayer/baseLayer';
import {
  ContextMenu,
  MapEventHandlers,
  handleRightClick,
  handleCopyCoordinates,
} from './ContextMenu';
import { defaultIcon, activeIcon } from '../icons';
import PanoLayer from './panoLayer/panoLayer';
import OrthoLayer from './orthoLayer/orthoLayer';
import { Map as LeafletMap } from 'leaflet';

interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

interface OrthoImageType {
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
  url: string;
}

interface MapContainerCanvasProps {
  selectedMarker: MarkerType | null;
  handleMarkerClick: (marker: MarkerType) => void;
  isVisible: boolean;
}

const MapContainerCanvas: React.FC<MapContainerCanvasProps> = ({
  selectedMarker,
  handleMarkerClick,
  isVisible,
}) => {
  const [markers, setMarkers] = useState<MarkerType[]>([]);
  const [mapCenter, setMapCenter] = useState<[number, number]>([55, 47]);
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean;
    x: number;
    y: number;
    lat: number;
    lng: number;
  }>({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });
  const [baseLayer, setBaseLayer] = useState<string>(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
  );
  const [showPanoLayer, setShowPanoLayer] = useState<boolean>(false);
  const [showOrthoLayer, setShowOrthoLayer] = useState<boolean>(false);
  const [orthoImages, setOrthoImages] = useState<OrthoImageType[]>([]);
  const [isSearchExpanded, setIsSearchExpanded] = useState<boolean>(false);

  const mapRef = useRef<LeafletMap | null>(null);

  const copyCoordinatesHandler = () => handleCopyCoordinates(contextMenu);

  // Компонент для установки mapRef.current
  const SetMapRef = () => {
    const map = useMap();
    useEffect(() => {
      mapRef.current = map;
    }, [map]);
    return null;
  };

  // Обработчик поиска координат
  const handleSearch = (searchInput: string) => {
    const coords = searchInput.split(',').map((coord) => parseFloat(coord.trim()));
    if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
      if (mapRef.current) {
        mapRef.current.setView(coords as [number, number], 18);
      }
      setMapCenter(coords as [number, number]);
    } else {
      alert('Неверный формат координат. Используйте формат: 59.333189, 57.128906');
    }
  };

  // Обработчик изменения базового слоя карты
  const handleLayerChange = (layerUrl: string) => {
    setBaseLayer(layerUrl);
  };

  // Переключатель слоя панорам
  const togglePanoLayer = (newMarkers: MarkerType[]) => {
    setShowPanoLayer(!showPanoLayer);
    setMarkers(newMarkers);
  };

  // Переключатель слоя ортофотопланов
  const toggleOrthoLayer = (newOrthoImages: OrthoImageType[]) => {
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
      },
    });
    return null;
  };

  return (
    <div
      style={{
        height: isVisible ? '50vh' : '100vh',
        width: '100%',
        position: 'relative',
      }}
    >
      <MapContainer
        center={mapCenter}
        zoom={5}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        maxZoom={22}
      >
        <SetMapRef />
        <TileLayer url={baseLayer} maxZoom={22} />
        {showPanoLayer && (
          <MarkerClusterGroup disableClusteringAtZoom={18} maxClusterRadius={50}>
            {markers.map((marker, index) => (
              <Marker
                position={[marker.lat, marker.lng]}
                key={`${marker.lat}-${marker.lng}-${index}`}
                icon={
                  selectedMarker &&
                  selectedMarker.lat === marker.lat &&
                  selectedMarker.lng === marker.lng
                    ? activeIcon
                    : defaultIcon
                }
                eventHandlers={{ click: () => handleMarkerClick(marker) }}
              />
            ))}
          </MarkerClusterGroup>
        )}
        {showOrthoLayer &&
          orthoImages.map((image, index) => (
            <ImageOverlay
              key={index}
              bounds={[
                [image.bounds.south, image.bounds.west],
                [image.bounds.north, image.bounds.east],
              ]}
              url={image.url}
            />
          ))}
        <ZoomControl position="bottomright" />
        <MapClickHandler />
        <MapEventHandlers setContextMenu={setContextMenu} />
      </MapContainer>
      <ContextMenu
        contextMenu={contextMenu}
        handleCopyCoordinates={copyCoordinatesHandler}
      />
      <Search
        handleSearch={handleSearch}
        isExpanded={isSearchExpanded}
        setIsExpanded={setIsSearchExpanded}
      />
      <BaseLayer handleLayerChange={handleLayerChange} />
      <PanoLayer togglePanoLayer={togglePanoLayer} />
      <OrthoLayer toggleOrthoLayer={toggleOrthoLayer} />
    </div>
  );
};

export default MapContainerCanvas;