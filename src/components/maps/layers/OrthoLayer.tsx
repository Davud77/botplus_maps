// src/components/maps/layers/OrthoLayer.tsx
import React from 'react';
import { TileLayer } from 'react-leaflet';
// [FIX] Исправлен путь импорта: поднимаемся на одну папку вверх (..) в maps, затем в hooks
import { useMapStore } from '../hooks/useMapStore';

import { API_BASE } from '../../../utils/api';

export const OrthoTileLayer = () => {
  // Теперь TypeScript видит типы из стора
  const { orthoImages, selectedOrthoIds } = useMapStore();

  return (
    <>
      {selectedOrthoIds.map((id) => {
        // id теперь автоматически определяется как number
        const ortho = orthoImages.find((o) => o.id === id);
        
        if (!ortho) return null;

        // ИСПОЛЬЗУЕМ НАШ БЭКЕНД ДЛЯ ПРОКСИРОВАНИЯ ТАЙЛОВ
        // Flask-бэкенд сам обратится к Titiler внутри Docker сети (по адресу из .env) 
        // и безопасно вернет готовую PNG картинку тайла на клиент.
        const tileUrl = `${API_BASE}/api/orthophotos/${id}/tiles/{z}/{x}/{y}.png`;

        return (
          <TileLayer
            key={id}
            url={tileUrl}
            maxZoom={24}
            maxNativeZoom={21}
            opacity={1}
            bounds={ortho.wgs84_bounds ? [
              [ortho.wgs84_bounds.south, ortho.wgs84_bounds.west],
              [ortho.wgs84_bounds.north, ortho.wgs84_bounds.east],
            ] : undefined}
            // [FIX] Удалено свойство transparent, так как оно вызывает ошибку TS 
            // и не требуется для обычных тайловых слоев (XYZ) с PNG.
          />
        );
      })}
    </>
  );
};