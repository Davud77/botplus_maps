// Файл: src/MarkerInfo.js
import React from 'react';

const MarkerInfo = ({ tags, latitude, longitude }) => {
  return (
    <div className="marker-info">
      <p>Выбранная метка: {tags}</p>
      <p>Широта: {latitude}</p>
      <p>Долгота: {longitude}</p>
    </div>
  );
};

export default MarkerInfo;
