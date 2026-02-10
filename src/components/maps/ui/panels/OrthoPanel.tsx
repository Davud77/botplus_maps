// src/components/maps/ui/panels/OrthoPanel.tsx

import React, { useEffect } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import L from 'leaflet';

// [FIX] Встроенная SVG заглушка (Data URI) для превью
const NO_IMAGE_PLACEHOLDER = `data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='150' viewBox='0 0 100 150'%3E%3Crect width='100' height='150' fill='%23eeeeee'/%3E%3Ctext x='50' y='75' font-family='sans-serif' font-size='12' text-anchor='middle' fill='%23999999'%3EOrtho%3C/text%3E%3C/svg%3E`;

interface OrthoPanelProps {
  onClose: () => void;
  map: L.Map | null;
}

export const OrthoPanel: React.FC<OrthoPanelProps> = ({ onClose, map }) => {
  const { orthoImages, selectedOrthoIds, isLoadingOrtho, fetchOrthos, toggleOrtho, fitToBounds } = useMapStore();

  useEffect(() => {
    fetchOrthos();
  }, []);

  return (
    <BasePanel title="Ортофотопланы" onClose={onClose}>
      {isLoadingOrtho && <div className="loading-state">Загрузка списка...</div>}
      
      {!isLoadingOrtho && orthoImages.length === 0 && (
        <div className="empty-state">Список пуст</div>
      )}

      <div className="ortho-list">
        {orthoImages.map(ortho => {
          const isActive = selectedOrthoIds.includes(ortho.id);
          
          return (
            <div key={ortho.id} className={`ortho-card ${isActive ? 'active-card' : ''}`}>
              
              {/* 1. Заголовок */}
              <div className="ortho-header" title={ortho.filename}>
                {ortho.filename}
              </div>

              {/* 2. Картинка (Заглушка) */}
              <div className="ortho-preview">
                <img 
                  // Если url ведет на tiff (скачивание), браузер не покажет его, сработает onError -> заглушка
                  src={ortho.url || NO_IMAGE_PLACEHOLDER} 
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
                    // Передаем карту явно для зума
                    if (map) fitToBounds(ortho.id, map); 
                  }}
                  title="Приблизить к слою"
                  disabled={!map}
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
                  // [FIX] ВАЖНО: Передаем map вторым аргументом!
                  onClick={() => toggleOrtho(ortho.id, map)}
                  title={isActive ? "Скрыть слой" : "Показать слой"}
                  disabled={!map} // Не даем кликать, пока карта не загрузилась
                >
                  {isActive ? (
                    // Открытый глаз
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  ) : (
                    // Закрытый глаз
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