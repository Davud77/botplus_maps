import { LayerPane } from './LayerPane';
// src/components/maps/layers/OrthoLayer.tsx
import React from 'react';
import RasterTileLayer from './RasterTileLayer';
// [FIX] Исправлен путь импорта: поднимаемся на одну папку вверх (..) в maps, затем в hooks
import { useMapStore } from '../hooks/useMapStore';

import { useLayerStyleStore } from '../hooks/useLayerStyleStore';
import { API_BASE } from '../../../utils/api';

export const OrthoTileLayer = () => {
  // Теперь TypeScript видит типы из стора
  const { orthoImages, selectedOrthoIds } = useMapStore();
  const {layers}=useLayerStyleStore();

  return (
    <>
      {selectedOrthoIds.map((id) => {
        // id теперь автоматически определяется как number
        const ortho = orthoImages.find((o) => o.id === id);
        
        const order=layers.findIndex(item=>item.key===`ortho:${id}`);
        const presentation=layers[order];
        if (!ortho || presentation?.visible===false) return null;

        // ИСПОЛЬЗУЕМ НАШ БЭКЕНД ДЛЯ ПРОКСИРОВАНИЯ ТАЙЛОВ
        // Flask-бэкенд сам обратится к Titiler внутри Docker сети (по адресу из .env) 
        // и безопасно вернет готовую PNG картинку тайла на клиент.
        const tileUrl = `${API_BASE}/api/orthophotos/${id}/tiles/{z}/{x}/{y}@2x.png`;

        return (
          <LayerPane key={id} name={`ortho-overlay-${id}`} style={{zIndex:400+layers.length-Math.max(order,0),opacity:presentation?.opacity??1}}><RasterTileLayer
            key={id}
            telemetryKey={`ortho:${id}`} label={ortho.filename}
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
          /></LayerPane>
        );
      })}
    </>
  );
};