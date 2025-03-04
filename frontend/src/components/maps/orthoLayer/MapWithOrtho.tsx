import React, { useState, useRef } from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import OrthoPanel from './OrthoPanel';
import { OrthoImageType } from './OrthoLayer';
import "leaflet/dist/leaflet.css";
import L from 'leaflet';

const MapWithOrtho: React.FC = () => {
  const [showOrtho, setShowOrtho] = useState(false);
  const [allOrthos, setAllOrthos] = useState<OrthoImageType[]>([]);
  const [selectedOrthos, setSelectedOrthos] = useState<OrthoImageType[]>([]);
  const mapRef = useRef<any>(null);

  // Загрузка ортофото при открытии панели
  const loadOrthoImages = async () => {
    try {
      const response = await fetch('https://api.botplus.ru//orthophotos');
      if (!response.ok) throw new Error(`Ошибка HTTP: ${response.status}`);
      const data = await response.json();
      setAllOrthos(data);
    } catch (err) {
      console.error('Ошибка при загрузке ортофото:', err);
    }
  };

  const handleToggleOrthoLayer = async () => {
    if (!showOrtho) {
      await loadOrthoImages();
    }
    setShowOrtho(prev => !prev);
  };

  const handleOrthoSelect = (ortho: OrthoImageType) => {
    setSelectedOrthos((prevSelected) => {
      const isSelected = prevSelected.some((o) => o.id === ortho.id);
      return isSelected 
        ? prevSelected.filter((o) => o.id !== ortho.id)
        : [...prevSelected, ortho];
    });
  };

  const fitToBounds = (ortho: OrthoImageType) => {
    if (!mapRef.current || !ortho.bounds) return;
    const sw = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.west, ortho.bounds.south));
    const ne = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.east, ortho.bounds.north));
    mapRef.current.fitBounds([sw, ne]);
  };

  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <button 
        className="ortho-toggle-button"
        onClick={handleToggleOrthoLayer}
      >
        {showOrtho ? 'Скрыть орто' : 'Показать орто'}
      </button>

      <MapContainer
        center={[55, 37]}
        zoom={5}
        style={{ width: '100%', height: '100%' }}
        ref={mapRef}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {selectedOrthos.map((ortho) => (
          <TileLayer
            key={ortho.id}
            url={`https://api.botplus.ru//orthophotos/${ortho.id}/tiles/{z}/{x}/{y}.png`}
            maxZoom={22}
            opacity={0.7}
          />
        ))}
      </MapContainer>

      {showOrtho && (
        <OrthoPanel
          onClose={() => setShowOrtho(false)}
          orthoImages={allOrthos}
          onOrthoSelect={handleOrthoSelect}
          selectedOrthos={selectedOrthos}
          fitToBounds={fitToBounds}
        />
      )}
    </div>
  );
};

export default MapWithOrtho;