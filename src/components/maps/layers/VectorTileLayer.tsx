import { workspaceRequest } from '../../../utils/workspaceApi';
import React, { useEffect, useRef } from 'react';
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
  pane?: string;
  coordinateUrl?: string;
}

const VectorTileLayer: React.FC<VectorTileLayerProps> = ({ url, styleConfigs, active, zIndex, pane, coordinateUrl }) => {
  const map = useMap();
  const coordinateUrlRef=useRef(coordinateUrl);
  useEffect(()=>{coordinateUrlRef.current=coordinateUrl;},[coordinateUrl]);

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

      pane: pane || 'overlayPane',
      zIndex: zIndex || 1
    };

    // Создаем слой
    const layer = L.vectorGrid.protobuf(url, vectorTileOptions);

    // --- 3. ПОПАП ---
    layer.on('click', (e: any) => {
        const props = e.layer.properties;
        const layerName = e.layer.options.layerName; // Имя таблицы (слоя)
        
        const container = document.createElement('div');
        container.className = 'vector-popup-container';
        const header = document.createElement('div');
        header.className = 'vector-popup-header';
        header.textContent = `Слой: ${layerName ?? ''}`;
        container.appendChild(header);
        const table = document.createElement('table');
        table.className = 'vector-popup-table';
        Object.entries(props).forEach(([key, value]) => {
          const row = table.insertRow();
          row.className = 'vector-popup-tr';
          const label = row.insertCell();
          label.className = 'vector-popup-key';
          label.textContent = `${key}:`;
          const cell = row.insertCell();
          cell.className = 'vector-popup-value';
          cell.textContent = value == null ? '' : String(value);
        });
        container.appendChild(table);
        const currentCoordinateUrl=coordinateUrlRef.current;
        if(currentCoordinateUrl) {
          const coordinates=document.createElement('p');
          coordinates.className='vector-popup-coordinates';
          coordinates.textContent='Пересчитываем координаты…';
          container.appendChild(coordinates);
          const point=e.latlng.wrap();
          workspaceRequest<{x:number;y:number;unit:string;name:string}>(`${currentCoordinateUrl}${currentCoordinateUrl.includes('?')?'&':'?'}lat=${point.lat}&lng=${point.lng}`).then(value=>{
            const decimals=value.unit==='°'?6:2;
            coordinates.textContent=`${value.name} · X ${value.x.toFixed(decimals)} · Y ${value.y.toFixed(decimals)} ${value.unit}`;
          }).catch(()=>{coordinates.textContent='Координаты в выбранной СК недоступны.';});
        }
        L.popup().setLatLng(e.latlng).setContent(container).openOn(map);

        L.DomEvent.stop(e); 
    });

    layer.addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [map, url, active, styleConfigs, zIndex, pane]); // Пересоздаем слой при изменении конфигов

  return null;
};

export default VectorTileLayer;