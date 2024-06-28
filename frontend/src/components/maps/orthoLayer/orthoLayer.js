import React, { useState, useEffect } from 'react';

const OrthoLayer = ({ toggleOrthoLayer }) => {
  const [orthoImages, setOrthoImages] = useState([]);

  useEffect(() => {
    fetch('https://api.botplus.ru/orthophotos')
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        setOrthoImages(data);
      })
      .catch(error => {
        console.error('Error fetching orthophotos:', error);
        alert('Не удалось загрузить данные об ортофотопланах.');
      });
  }, []);

  return (
    <button className="layers-button" onClick={() => toggleOrthoLayer(orthoImages)} style={{ position: 'absolute', top: '210px', right: '14px', zIndex: 1000 }}>
      <svg xmlns="http://www.w3.org/2000/svg" height="30px" viewBox="0 0 24 24" width="30px" fill="#fff">
        <path d="M0 0h24v24H0V0z" fill="none"/>
        <path d="M21 10.78V9c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v1.78C2.39 11.15 2 12.02 2 13v6c0 1.1.9 2 2 2h1v1c0 .55.45 1 1 1s1-.45 1-1v-1h10v1c0 .55.45 1 1 1s1-.45 1-1v-1h1c1.1 0 2-.9 2-2v-6c0-.98-.39-1.85-1-2.22zm-2 7.22H5v-5c0-.55.45-1 1-1h12c.55 0 1 .45 1 1v5zm-3.75-4.25c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3zm0 4c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-11.5-4c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3zm0 4c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm5-6V7h6v2h-6z"/>
      </svg>
    </button>
  );
};

export default OrthoLayer;
