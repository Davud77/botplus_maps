// src/components/maps/ui/panels/OrthoPanel.tsx

import React, { useEffect, useState } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import L from 'leaflet';

// Встроенная SVG заглушка (Data URI) для превью
const NO_IMAGE_PLACEHOLDER = `data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='150' viewBox='0 0 100 150'%3E%3Crect width='100' height='150' fill='%23eeeeee'/%3E%3Ctext x='50' y='75' font-family='sans-serif' font-size='12' text-anchor='middle' fill='%23999999'%3EOrtho%3C/text%3E%3C/svg%3E`;

interface OrthoPanelProps {
  onClose: () => void;
  map: L.Map | null;
}

// Конвертер координат: из метров EPSG:3857 в градусы WGS84 (Leaflet LatLngBounds)
const normalizeBounds = (bounds: any, crs?: string): L.LatLngBounds | null => {
  if (!bounds) return null;

  // Если координаты уже похожи на градусы WGS84 (широта <= 90, долгота <= 180)
  if (Math.abs(bounds.south) <= 90 && Math.abs(bounds.west) <= 180) {
    return L.latLngBounds([bounds.south, bounds.west], [bounds.north, bounds.east]);
  }

  // Если координаты в метрах Web Mercator (EPSG:3857)
  if (crs && (crs.includes('3857') || crs.includes('Pseudo-Mercator') || crs.includes('Google'))) {
    const toLat = (y: number) => (180 / Math.PI) * (2 * Math.atan(Math.exp((y / 20037508.34) * Math.PI)) - Math.PI / 2);
    const toLng = (x: number) => (x / 20037508.34) * 180;
    
    return L.latLngBounds(
      [toLat(bounds.south), toLng(bounds.west)],
      [toLat(bounds.north), toLng(bounds.east)]
    );
  }

  // Если это локальная МСК в метрах, которую мы не можем перевести без proj4
  return null;
};

export const OrthoPanel: React.FC<OrthoPanelProps> = ({ onClose, map }) => {
  const { orthoImages, selectedOrthoIds, isLoadingOrtho, fetchOrthos, toggleOrtho } = useMapStore();
  
  // Состояние для хранения текущих границ карты
  const [mapBounds, setMapBounds] = useState<L.LatLngBounds | null>(null);

  useEffect(() => {
    fetchOrthos();
  }, []);

  // Отслеживание перемещения карты для обновления границ
  useEffect(() => {
    if (!map) return;

    // Устанавливаем начальные границы
    setMapBounds(map.getBounds());

    const handleMoveEnd = () => {
      setMapBounds(map.getBounds());
    };

    // Слушаем события перемещения и зума
    map.on('moveend', handleMoveEnd);
    map.on('zoomend', handleMoveEnd);

    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleMoveEnd);
    };
  }, [map]);

  // Фильтрация списка ортофотопланов
  const filteredOrthos = orthoImages.filter(ortho => {
    // 1. Базовая проверка: слой должен быть включен в БД
    if (!ortho.is_visible) return false;
    
    // 2. Проверяем пересечение с экраном карты
    if (ortho.bounds && mapBounds) {
      const orthoLatLngBounds = normalizeBounds(ortho.bounds, ortho.crs);
      
      // Если смогли перевести координаты в градусы — фильтруем
      if (orthoLatLngBounds) {
        return mapBounds.intersects(orthoLatLngBounds);
      }
      
      // Если координаты в МСК (не перевелись), просто показываем файл, чтобы он не пропал
      return true;
    }
    
    return false;
  });

  return (
    <BasePanel title="Ортофотопланы" onClose={onClose}>
      {isLoadingOrtho && <div className="loading-state">Загрузка списка...</div>}
      
      {!isLoadingOrtho && filteredOrthos.length === 0 && (
        <div className="empty-state">В данной области нет видимых слоев</div>
      )}

      <div className="ortho-list">
        {filteredOrthos.map(ortho => {
          const isActive = selectedOrthoIds.includes(ortho.id);
          
          return (
            <div key={ortho.id} className={`ortho-card ${isActive ? 'active-card' : ''}`}>
              
              {/* 1. Заголовок */}
              <div className="ortho-header" title={ortho.filename}>
                {ortho.filename}
              </div>

              {/* 2. Картинка (Превью) */}
              <div className="ortho-preview">
                <img className="ortho-preview-img"
                  // Используем легкую миниатюру вместо тяжелого tiff
                  src={ortho.preview_url || NO_IMAGE_PLACEHOLDER} 
                  alt="preview"
                  onError={(e) => { (e.target as HTMLImageElement).src = NO_IMAGE_PLACEHOLDER; }}
                />
                {isActive && <div className="active-badge"></div>}
              </div>

              {/* 3. Панель действий */}
              <div className="ortho-actions">
                {/* Кнопка: Показать на карте (Зум) */}
                <button 
                  className="action-btn zoom-btn"
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    if (map && ortho.bounds) {
                       const boundsToZoom = normalizeBounds(ortho.bounds, ortho.crs);
                       if (boundsToZoom) map.fitBounds(boundsToZoom);
                    }
                  }}
                  title="Приблизить к слою"
                  disabled={!map || !ortho.bounds}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    <line x1="11" y1="8" x2="11" y2="14"></line>
                    <line x1="8" y1="11" x2="14" y2="11"></line>
                  </svg>
                </button>

                <div className="divider"></div>

                {/* Кнопка: Глаз (Вкл/Выкл) */}
                <button 
                  className={`action-btn eye-btn ${isActive ? 'visible' : ''}`}
                  onClick={() => toggleOrtho(ortho.id, map)}
                  title={isActive ? "Скрыть слой" : "Показать слой"}
                  disabled={!map} 
                >
                  {isActive ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M1 1l22 22"></path>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path>
                    </svg>
                  )}
                </button>
              </div>

            </div>
          );
        })}
      </div>
    </BasePanel>
  );
};