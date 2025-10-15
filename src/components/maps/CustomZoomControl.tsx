import React, { useCallback } from 'react';
import { useMap } from 'react-leaflet';
import type { Map as LeafletMap } from 'leaflet';
import '../../assets/css/ZoomControl.css';

const CustomZoomControl: React.FC = () => {
  const map = useMap() as LeafletMap;

  // Увеличение
  const handleZoomIn = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    map.zoomIn();
  }, [map]);

  // Уменьшение
  const handleZoomOut = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    map.zoomOut();
  }, [map]);

  // Добавляем класс "active" при начале тач-события
  const handleTouchStart = useCallback((e: React.TouchEvent<HTMLButtonElement>) => {
    e.currentTarget.classList.add('active');
  }, []);

  // Убираем класс "active" при окончании тач-события
  const handleTouchEnd = useCallback((e: React.TouchEvent<HTMLButtonElement>) => {
    e.currentTarget.classList.remove('active');
  }, []);

  return (
    <div className="custom-zoom-container">
      <button
        type="button"
        className="custom-zoom-btn zoom-in"
        onClick={handleZoomIn}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        aria-label="Увеличить масштаб карты"
        title="Увеличить"
      >
        <span className="zoom-symbol plus">+</span>
      </button>

      <button
        type="button"
        className="custom-zoom-btn zoom-out"
        onClick={handleZoomOut}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        aria-label="Уменьшить масштаб карты"
        title="Уменьшить"
      >
        <span className="zoom-symbol minus">-</span>
      </button>
    </div>
  );
};

export default CustomZoomControl;