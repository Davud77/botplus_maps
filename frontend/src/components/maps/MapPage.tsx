// src/components/maps/MapPage.tsx

import React, { useState, useCallback } from 'react';
import PanoramaViewer from './panoLayer/PanoramaViewer';
import Header from '../Header';
import MapContainerCanvas from './MapContainerCanvas';

interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

const MapPage: React.FC = () => {
  const [selectedMarker, setSelectedMarker] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  const handleMarkerClick = useCallback((marker: MarkerType) => {
    setSelectedMarker(marker.id);
    setIsVisible(true);
  }, []);

  const toggleHeight = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const closeInfo = useCallback(() => {
    setIsVisible(false);
  }, []);

  return (
    <div>
      <Header />
      {selectedMarker && isVisible && (
        <div className="selected-marker-info" style={{ height: isExpanded ? '100%' : '50%' }}>
          <PanoramaViewer markerId={selectedMarker} isExpanded={isExpanded} />
          <div className="visible_control">
            <button className="button button_control" onClick={toggleHeight}>
              <img src={isExpanded ? '/images/collapse.png' : '/images/expand.png'} alt={isExpanded ? 'Свернуть' : 'Развернуть'} />
            </button>
            <button className="button button_control" onClick={closeInfo}>
              <img src="/images/close.png" alt="Закрыть" />
            </button>
          </div>
        </div>
      )}
      <div className="MapContainerCanvas">
        <MapContainerCanvas
          selectedMarker={selectedMarker ? { id: selectedMarker, lat: 0, lng: 0 } : null}
          handleMarkerClick={handleMarkerClick}
          isVisible={isVisible}
        />
      </div>
    </div>
  );
};

export default MapPage;