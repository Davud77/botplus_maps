import React from 'react';
import { TileLayer } from 'react-leaflet';
import { useMapStore } from '../hooks/useMapStore';

export const OrthoTileLayer = () => {
  const { orthoImages, selectedOrthoIds } = useMapStore();

  return (
    <>
      {selectedOrthoIds.map(id => {
        // Находим объект ортофото по ID, чтобы получить URL (если нужно)
        // В данном случае URL API предсказуем
        return (
          <TileLayer
            key={id}
            url={`https://api.botplus.ru/orthophotos/${id}/tiles/{z}/{x}/{y}.png`}
            maxZoom={22}
            opacity={0.7}
          />
        );
      })}
    </>
  );
};