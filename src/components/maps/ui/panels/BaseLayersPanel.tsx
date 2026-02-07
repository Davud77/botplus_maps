import React from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';

interface LayerOption {
  name: string;
  url: string;
  image: string; // Путь к картинке-превью
  attribution?: string;
}

const LAYERS: LayerOption[] = [
  // --- 1. Основные (Google & OSM) ---
  { 
    name: "Google Hybrid", 
    url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", 
    image: "/images/GoogleHybrid.png" 
  },
  { 
    name: "Google Satellite", 
    url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", 
    image: "/images/GoogleSatellite.png" 
  },
  { 
    name: "Google Maps", 
    url: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", 
    image: "/images/GoogleMaps.png" 
  },
  { 
    name: "OSM Standard", 
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", 
    image: "/images/OSM.png" 
  },

  // --- 2. ESRI (Отличное качество для архитектуры) ---
  { 
    name: "Esri Satellite", 
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 
    image: "/images/EsriSat.png" 
  },
  { 
    name: "Esri Streets", 
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", 
    image: "/images/EsriStreet.png" 
  },
  { 
    name: "Esri Topo", 
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", 
    image: "/images/EsriTopo.png" 
  },

  // --- 3. Яндекс (Специфическая проекция, но часто работает) ---
  { 
    name: "Yandex Satellite", 
    url: "https://core-sat.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&scale=1&lang=ru_RU", 
    image: "/images/YandexSat.png" 
  },
  { 
    name: "Yandex Maps", 
    url: "https://vec01.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&scale=1&lang=ru_RU", 
    image: "/images/YandexMap.png" 
  },

  // --- 4. Стильные / Минимализм (Для наложения CAD данных) ---
  { 
    name: "CartoDB Dark", 
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png", 
    image: "/images/CartoDBDarkMatter.png" 
  },
  { 
    name: "CartoDB Voyager", 
    url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", 
    image: "/images/CartoVoyager.png" // Светлая, приятная карта
  },
  { 
    name: "CartoDB Positron", 
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", 
    image: "/images/CartoPositron.png" // Почти белая, хороший фон
  },

  // --- 5. Топография и Ландшафт ---
  { 
    name: "OpenTopoMap", 
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", 
    image: "/images/OpenTopo.png" 
  },
  { 
    name: "CyclOSM", 
    url: "https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png", 
    image: "/images/CyclOSM.png" // Хороший контраст улиц
  },
  { 
    name: "Wikimedia", 
    url: "https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png", 
    image: "/images/Wiki.png" // Без лишнего шума
  }
];

export const BaseLayersPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  // Получаем текущий url и функцию смены из стора
  // Убедитесь, что в useMapStore есть setBaseLayer(url: string)
  const { baseLayerUrl, setBaseLayer } = useMapStore();

  const handleLayerSelect = (layer: LayerOption) => {
    setBaseLayer(layer.url);
    // Опционально: можно закрывать панель при выборе
    // onClose(); 
  };

  return (
    <BasePanel title="Слои карты" onClose={onClose}>
      <div className="layers-container">
        <div className="layers-grid">
          {LAYERS.map((layer) => (
            <div 
              key={layer.name} 
              className={`layer-card ${baseLayerUrl === layer.url ? 'active' : ''}`}
              onClick={() => handleLayerSelect(layer)}
            >
              <div className="image-wrapper">
                <img 
                  src={layer.image} 
                  alt={layer.name} 
                  // Если картинки нет, показываем заглушку с названием
                  onError={(e) => {
                    const target = e.currentTarget;
                    target.onerror = null; // Предотвращаем бесконечный цикл
                    target.src = `https://placehold.co/100x60/e0e0e0/333?text=${layer.name.replace(' ', '+')}`;
                  }} 
                />
                <div className="layer-name">{layer.name}</div>
              </div>
              
              {/* Индикатор активного слоя */}
              {baseLayerUrl === layer.url && (
                <div className="active-indicator">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <style>{`
        /* Контейнер для скролла, если слоев много */
        .layers-container {
          max-height: 400px; /* Ограничиваем высоту */
          overflow-y: auto;  /* Добавляем скролл */
          padding-right: 4px; /* Отступ для скроллбара */
        }

        /* Кастомизация скроллбара (опционально) */
        .layers-container::-webkit-scrollbar { width: 6px; }
        .layers-container::-webkit-scrollbar-track { background: #f1f1f1; }
        .layers-container::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

        .layers-grid { 
          display: grid; 
          grid-template-columns: 1fr 1fr; 
          gap: 10px; 
          padding-bottom: 10px;
        }

        .layer-card { 
          position: relative; 
          cursor: pointer; 
          border-radius: 8px; 
          overflow: hidden; 
          border: 2px solid transparent; 
          transition: all 0.2s ease;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .layer-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 6px rgba(0,0,0,0.15);
        }

        .layer-card.active { 
          border-color: #2196F3; 
          box-shadow: 0 0 0 1px #2196F3;
        }

        .image-wrapper { 
          position: relative; 
          height: 80px; 
          background: #eee;
        }

        .image-wrapper img { 
          width: 100%; 
          height: 100%; 
          object-fit: cover; 
          display: block;
        }

        .layer-name {
          position: absolute; 
          bottom: 0; 
          left: 0; 
          right: 0;
          background: linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0)); 
          color: white; 
          font-size: 11px;
          font-weight: 500;
          padding: 8px 4px 4px; 
          text-align: center;
          text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }

        .active-indicator {
          position: absolute; 
          top: 6px; 
          right: 6px; 
          background: #2196F3;
          color: white; 
          width: 20px; 
          height: 20px; 
          border-radius: 50%;
          display: flex; 
          align-items: center; 
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
          animation: popIn 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        @keyframes popIn {
          from { transform: scale(0); }
          to { transform: scale(1); }
        }
      `}</style>
    </BasePanel>
  );
};