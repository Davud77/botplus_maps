import React from 'react';

interface PanoLayerButtonProps {
  handlePanoLayerToggle: () => void;
  isLoading?: boolean;
}

const PanoLayerButton: React.FC<PanoLayerButtonProps> = ({ handlePanoLayerToggle, isLoading }) => {
  return (
    <button 
      className="layers-button" 
      onClick={handlePanoLayerToggle}
      title="Показать панорамы"
    >
      <img 
        src="/images/svg/pano-layer-icon.svg" 
        alt="Слой панорам"
        width="30"
        height="30"
      />
      {isLoading && (
        <div className="loading-indicator">
          <span className="spinner"></span>
        </div>
      )}
    </button>
  );
};

export default PanoLayerButton; 