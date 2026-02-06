import React, { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
// Импортируем библиотеку (убедитесь, что она установлена: npm install leaflet.vectorgrid)
import 'leaflet.vectorgrid'; 

// --- FIX: Polyfill for Leaflet 1.8+ and VectorGrid ---
// Библиотека vectorgrid использует удаленный метод fakeStop. 
// Мы возвращаем его, приравнивая к stopPropagation.
if (!(L.DomEvent as any).fakeStop) {
  (L.DomEvent as any).fakeStop = L.DomEvent.stopPropagation;
}
// ---------------------------------------------------

// Если TypeScript ругается на L.vectorGrid, добавляем декларацию
declare module 'leaflet' {
  namespace vectorGrid {
    function protobuf(url: string, options?: any): any;
  }
}

interface VectorTileLayerProps {
  url: string;      // Ссылка на API тайлов (комбинированная)
  // [ИЗМЕНЕНО] Теперь принимаем объект стилей: { 'layerName': { style... }, ... }
  styles: Record<string, any>; 
  active: boolean;
  zIndex?: number;
}

const VectorTileLayer: React.FC<VectorTileLayerProps> = ({ url, styles, active, zIndex }) => {
  const map = useMap();

  useEffect(() => {
    if (!active) return;

    // Опции для VectorGrid
    const vectorTileOptions = {
      // ИСПРАВЛЕНИЕ: (L.canvas as any).tile, так как TS не знает про расширение .tile
      rendererFactory: (L.canvas as any).tile,
      
      // [ВАЖНО] Передаем весь объект стилей.
      // Ключи объекта styles должны совпадать с именами таблиц (слоев) в PBF.
      vectorTileLayerStyles: styles,
      
      interactive: true, // Разрешаем клики и наведение
      
      // Функция получения уникального ID фичи (важно для оптимизации рендеринга)
      getFeatureId: (f: any) => {
        return f.properties.id || f.id || 0;
      },

      zIndex: zIndex || 1
    };

    // Создаем слой тайлов
    const layer = L.vectorGrid.protobuf(url, vectorTileOptions);

    // Обработчик клика: Показываем свойства объекта
    layer.on('click', (e: any) => {
        const props = e.layer.properties;
        
        // Формируем красивый HTML для попапа
        L.popup()
          .setLatLng(e.latlng)
          .setContent(`
            <div style="font-size:12px; max-width:250px; max-height:300px; overflow-y:auto;">
              <h4 style="margin:0 0 5px 0;">Свойства объекта</h4>
              <table style="width:100%; border-collapse: collapse;">
                ${Object.entries(props).map(([k, v]) => `
                  <tr style="border-bottom: 1px solid #eee;">
                    <td style="font-weight:bold; padding:2px 5px; vertical-align:top;">${k}:</td>
                    <td style="padding:2px 5px; word-break:break-word;">${String(v)}</td>
                  </tr>
                `).join('')}
              </table>
            </div>
          `)
          .openOn(map);
          
        // Останавливаем всплытие события, чтобы не кликнуть "сквозь" объект по карте
        L.DomEvent.stop(e); 
    });

    // Добавляем слой на карту
    layer.addTo(map);

    // Очистка при размонтировании или изменении пропсов
    return () => {
      map.removeLayer(layer);
    };
  }, [map, url, active, styles]); // Пересоздаем слой при изменении URL или набора стилей

  return null;
};

export default VectorTileLayer;