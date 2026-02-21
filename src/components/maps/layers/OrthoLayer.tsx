// src/components/maps/layers/OrthoLayer.tsx
import React from 'react';
import { TileLayer } from 'react-leaflet';
// [FIX] Исправлен путь импорта: поднимаемся на одну папку вверх (..) в maps, затем в hooks
import { useMapStore } from '../hooks/useMapStore';

// Определяем базовый URL API так же, как в api.ts
// Если мы разрабатываем локально, стучимся на порт бэкенда.
// Если на проде (botplus.ru), используем относительный путь, и Nginx сам проксирует запрос.
const isLocalhost = 
  typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
const API_BASE = isLocalhost ? 'http://localhost:5580' : '';

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
            // [FIX] Удалено свойство transparent, так как оно вызывает ошибку TS 
            // и не требуется для обычных тайловых слоев (XYZ) с PNG.
          />
        );
      })}
    </>
  );
};