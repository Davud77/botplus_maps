import React, { useState, useEffect, useCallback } from 'react';
import PanoramaViewer from './PanoramaViewer';
import MarkerInfo from './MarkerInfo';
import Header from './Header';
import MapContainerCanvas from './MapContainerCanvas';

const MapPage = () => {
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [mapCenter] = useState([55, 47]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

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
          <MarkerInfo tags={selectedMarker.tags} latitude={selectedMarker.lat} longitude={selectedMarker.lng} />
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
          markers={markers}
          selectedMarker={selectedMarker}
          handleMarkerClick={handleMarkerClick}
          mapCenter={mapCenter}
        />
      </div>
    </div>
  );
};

export default MapPage;
