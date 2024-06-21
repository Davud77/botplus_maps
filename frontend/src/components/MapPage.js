import React, { useState, useCallback } from 'react';
import PanoramaViewer from './PanoramaViewer';

import Header from './Header';
import MapContainerCanvas from './MapContainerCanvas';

const MapPage = () => {
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  const handleMarkerClick = useCallback((marker) => {
    setSelectedMarker(marker);
    setIsVisible(true);
  }, []);

  const toggleHeight = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  const closeInfo = useCallback(() => {
    setIsVisible(false);
  }, []);

  return (
    <div>
      <Header />
      {selectedMarker && isVisible && (
        <div className="selected-marker-info" style={{ height: isExpanded ? '100%' : '50%' }}>
          <PanoramaViewer imageUrl={selectedMarker.imageUrl} isExpanded={isExpanded} />
          
          <div className="visible_control">
            <button className="button button_control" onClick={toggleHeight}>
              <img src={isExpanded ? "/images/collapse.png" : "/images/expand.png"} alt={isExpanded ? "Свернуть" : "Развернуть"} />
            </button>
            <button className="button button_control" onClick={closeInfo}>
              <img src="/images/close.png" alt="Закрыть" />
            </button>
          </div>
        </div>
      )}
      <div className="MapContainerCanvas">
        <MapContainerCanvas 
          selectedMarker={selectedMarker}
          handleMarkerClick={handleMarkerClick}
          isVisible={isVisible}
        />
      </div>
    </div>
  );
};

export default MapPage;
