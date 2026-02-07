import React from 'react';
import { TileLayer } from 'react-leaflet';
// [FIX] Исправлен путь импорта: поднимаемся на одну папку вверх (..) в maps, затем в hooks
import { useMapStore } from '../hooks/useMapStore';

const TITILER_URL = 'http://localhost:8000';

export const OrthoTileLayer = () => {
  // Теперь TypeScript видит типы из стора
  const { orthoImages, selectedOrthoIds } = useMapStore();

  return (
    <>
      {selectedOrthoIds.map((id) => {
        // id теперь автоматически определяется как number
        const ortho = orthoImages.find((o) => o.id === id);
        
        if (!ortho) return null;

        const s3Url = `s3://orthophotos/${ortho.filename}`;
        
        // Формируем URL. Обратите внимание, что transparent не нужен в URL, 
        // так как PNG по умолчанию поддерживают альфа-канал.
        const tileUrl = `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}@1x?url=${encodeURIComponent(s3Url)}`;

        return (
          <TileLayer
            key={id}
            url={tileUrl}
            maxZoom={24}
            maxNativeZoom={21}
            opacity={1}
            // [FIX] Удалено свойство transparent, так как оно вызывает ошибку TS 
            // и не требуется для обычных тайловых слоев (XYZ) с PNG.
          />
        );
      })}
    </>
  );
};