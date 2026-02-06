// src/components/maps/ui/MapButtons.tsx
import React from 'react';
import { useUIStore, PanelType } from '../hooks/useUIStore';

interface MapButtonsProps {
  onTogglePano: () => void;
  isPanoLoading?: boolean;
}

export const MapButtons: React.FC<MapButtonsProps> = ({ onTogglePano, isPanoLoading }) => {
  const { activePanel, togglePanel } = useUIStore();

  /**
   * Вспомогательная функция для рендеринга кнопок.
   */
  const renderBtn = (panel: PanelType, iconSrc: string, title: string) => (
    <button 
      className={`layers-button ${activePanel === panel ? 'active' : ''}`} 
      onClick={() => togglePanel(panel)}
      title={title}
    >
      <img src={iconSrc} alt={title} width="24" height="24" />
    </button>
  );

  return (
    <div className="map-buttons-container">
      {/* Базовые слои — открывает BaseLayersPanel */}
      {renderBtn('baseLayers', '/images/svg/layers-icon.svg', 'Слои карты')}
      
      {/* Панорамы.
         Используем (activePanel as string) и ('pano' as any), чтобы избежать ошибок TypeScript,
         пока 'pano' не добавлено в PanelType в useUIStore.
      */}
      <button 
        className={`layers-button ${(activePanel as string) === 'pano' ? 'active' : ''}`} 
        onClick={() => {
          // Открываем панель (приводим тип для совместимости)
          togglePanel('pano' as any); 
          // Включаем слой точек на карте
          onTogglePano();      
        }} 
        title="Панорамы"
      >
        <img src="/images/svg/pano-layer-icon.svg" alt="Панорамы" width="24" height="24" />
        {isPanoLoading && <span className="spinner-small" />}
      </button>

      {/* Ортофото — открывает OrthoPanel */}
      {renderBtn('ortho', '/images/svg/ortho-icon.svg', 'Ортофотопланы')}

      {/* Векторы — открывает VectorPanel */}
      {renderBtn('vector', '/images/svg/vector.svg', 'Векторные слои')}
    </div>
  );
};