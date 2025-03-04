import React, { useState, useEffect } from 'react';

interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

interface PanoLayerProps {
  togglePanoLayer: (newMarkers: MarkerType[]) => void;
}

const PanoLayer: React.FC<PanoLayerProps> = ({ togglePanoLayer }) => {
  const [markers, setMarkers] = useState<MarkerType[]>([]);

  useEffect(() => {
    fetch('https://api.botplus.ru/panoramas')
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: any[]) => {
        const newMarkers = data.map((item: any) => ({
          id: item.id,
          lat: item.latitude,
          lng: item.longitude,
        }));
        setMarkers(newMarkers);
      })
      .catch(error => {
        console.error('Error fetching panoramas:', error);
        alert('Не удалось загрузить данные о панорамах.');
      });
  }, []);

  return (
    <button className="layers-button" onClick={() => togglePanoLayer(markers)}>
      <img 
        src="/images/svg/pano-layer-icon.svg" 
        alt="Слой панорам"
        width="30"
        height="30"
      />
    </button>
  );
};

export default PanoLayer;
