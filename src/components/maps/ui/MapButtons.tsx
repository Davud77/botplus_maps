import React from 'react';
import { useUIStore, PanelType } from '../hooks/useUIStore';


interface MapButtonsProps {
  onTogglePano: () => void;
  isPanoLoading?: boolean;
}

export const MapButtons: React.FC<MapButtonsProps> = ({ onTogglePano, isPanoLoading }) => {
  const { activePanel, togglePanel } = useUIStore();

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
      {/* Базовые слои */}
      {renderBtn('baseLayers', '/images/svg/layers-icon.svg', 'Слои карты')}
      
      {/* Панорамы */}
      <button className="layers-button" onClick={onTogglePano} title="Панорамы">
        <img src="/images/svg/pano-layer-icon.svg" alt="Панорамы" width="24" height="24" />
        {isPanoLoading && <span className="spinner-small" />}
      </button>

      {/* Ортофото */}
      {renderBtn('ortho', '/images/svg/ortho-icon.svg', 'Ортофотопланы')}

      {/* Векторы */}
      <button 
        className={`layers-button ${activePanel === 'vector' ? 'active' : ''}`}
        
        onClick={() => togglePanel('vector')}
        title="Векторные слои"
      >
        <img src="/images/svg/vector.svg" alt="Векторные слои" width="24" height="24" />
        
      </button>
    </div>
  );
};