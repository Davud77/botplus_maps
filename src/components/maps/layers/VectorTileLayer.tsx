import React, { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
// Импортируем библиотеку (убедитесь, что она установлена: npm install leaflet.vectorgrid)
import 'leaflet.vectorgrid'; 

// --- FIX: Polyfill for Leaflet 1.8+ and VectorGrid ---
if (!(L.DomEvent as any).fakeStop) {
  (L.DomEvent as any).fakeStop = L.DomEvent.stopPropagation;
}
// ---------------------------------------------------

// Типизация модуля leaflet.vectorgrid
declare module 'leaflet' {
  namespace vectorGrid {
    function protobuf(url: string, options?: any): any;
  }
}

// --- Типы для конфигурации стилей ---
interface StyleRule {
  value: string | number;
  style: L.PathOptions;
}

interface LayerStyleConfig {
  type: 'single' | 'categorized';
  field?: string;       // Поле, по которому идет категоризация
  rules?: StyleRule[];  // Правила: значение -> стиль
  style?: L.PathOptions; // Базовый стиль (или fallback)
}

interface VectorTileLayerProps {
  url: string; 
  // [ИЗМЕНЕНО] Принимаем конфигурацию, а не готовые стили Leaflet
  styleConfigs: Record<string, LayerStyleConfig>; 
  active: boolean;
  zIndex?: number;
}

const VectorTileLayer: React.FC<VectorTileLayerProps> = ({ url, styleConfigs, active, zIndex }) => {
  const map = useMap();

  useEffect(() => {
    if (!active) return;

    // --- 1. ГЕНЕРАЦИЯ СТИЛЕЙ LEAFLET ---
    // Превращаем наши JSON-конфиги в то, что понимает VectorGrid (объекты или функции)
    const vectorTileLayerStyles: Record<string, any> = {};

    Object.keys(styleConfigs).forEach((layerName) => {
      const config = styleConfigs[layerName];

      if (config.type === 'categorized' && config.field && config.rules) {
        // === ДИНАМИЧЕСКАЯ СТИЛИЗАЦИЯ (Categorized) ===
        // VectorGrid будет вызывать эту функцию для КАЖДОГО объекта
        vectorTileLayerStyles[layerName] = (properties: any, zoom: number) => {
          const val = properties[config.field!]; // Значение поля объекта (например, 'highway')
          
          // Ищем правило. Приводим к строке для надежного сравнения (xml vs json number)
          const rule = config.rules?.find((r) => String(r.value) === String(val));
          
          if (rule) {
            return rule.style;
          }
          
          // Если правило не найдено — возвращаем дефолтный стиль (серый)
          return config.style || { color: '#aaaaaa', fillOpacity: 0.2, weight: 1 };
        };
      } else {
        // === ОБЫЧНАЯ СТИЛИЗАЦИЯ (Single) ===
        vectorTileLayerStyles[layerName] = config.style || { color: '#3388ff', weight: 1 };
      }
    });

    // --- 2. НАСТРОЙКИ VECTORGRID ---
    const vectorTileOptions = {
      rendererFactory: (L.canvas as any).tile,
      
      // Передаем сгенерированный объект стилей (где могут быть функции)
      vectorTileLayerStyles: vectorTileLayerStyles,
      
      interactive: true,
      
      getFeatureId: (f: any) => {
        return f.properties.id || f.id || 0;
      },

      zIndex: zIndex || 1
    };

    // Создаем слой
    const layer = L.vectorGrid.protobuf(url, vectorTileOptions);

    // --- 3. ПОПАП ---
    layer.on('click', (e: any) => {
        const props = e.layer.properties;
        const layerName = e.layer.options.layerName; // Имя таблицы (слоя)
        
        L.popup()
          .setLatLng(e.latlng)
          .setContent(`
            <div class="vector-popup-container">
              <div class="vector-popup-header">
                <strong>Слой:</strong> ${layerName}
              </div>
              <table class="vector-popup-table">
                ${Object.entries(props).map(([k, v]) => `
                  <tr class="vector-popup-tr">
                    <td class="vector-popup-key">${k}:</td>
                    <td class="vector-popup-value">${v !== null && v !== undefined ? String(v) : ''}</td>
                  </tr>
                `).join('')}
              </table>
            </div>
          `)
          .openOn(map);
          
        L.DomEvent.stop(e); 
    });

    layer.addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [map, url, active, styleConfigs]); // Пересоздаем слой при изменении конфигов

  return null;
};

export default VectorTileLayer;