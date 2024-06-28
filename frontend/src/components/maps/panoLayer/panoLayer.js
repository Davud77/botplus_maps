import React, { useState, useEffect } from 'react';

const PanoLayer = ({ togglePanoLayer }) => {
  const [markers, setMarkers] = useState([]);

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
          id: item.id,
          lat: item.latitude,
          lng: item.longitude
        }));
        setMarkers(newMarkers);
      })
      .catch(error => {
        console.error('Error fetching panoramas:', error);
        alert('Не удалось загрузить данные о панорамах.');
      });
  }, []);

  return (
    <button className="layers-button" onClick={() => togglePanoLayer(markers)} style={{ position: 'absolute', top: '145px', right: '14px', zIndex: 1000 }}>
      <svg xmlns="http://www.w3.org/2000/svg" height="30px" viewBox="0 0 24 24" width="30px" fill="#fff">
        <path d="M0 0h24v24H0V0z" fill="none"/>
        <path d="M12 2.1c5.47 0 10.5 2.23 10.5 5v2.17c0 1.49-.81 2.91-2.18 4.13a12.06 12.06 0 0 1-4.32 2.43L12 19.9l-4-2.27c-2.42-.82-4.32-2.12-5.5-3.54A6.32 6.32 0 0 1 2 9.17V7.1c0-2.77 5.03-5 10.5-5zM4.14 9.69a4.32 4.32 0 0 0 1.86 2.81c.99.7 2.24 1.26 3.68 1.54l.64.18.64-.18c1.44-.28 2.69-.84 3.68-1.54a4.32 4.32 0 0 0 1.86-2.81c-.34.08-.68.13-1.04.13-1.27 0-2.41-.33-3.5-.97-1.09.64-2.23.97-3.5.97-.36 0-.7-.05-1.04-.13z"/>
      </svg>
    </button>
  );
};

export default PanoLayer;
