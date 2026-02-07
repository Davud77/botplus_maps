import React, { useEffect } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import L from 'leaflet';

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
                {/* В будущем сюда можно подставить реальный URL превью */}
                <img 
                  src={`https://placehold.co/100x150/eef2f5/909090?text=Ortho+Preview`} 
                  alt="preview" 
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
                  onClick={() => toggleOrtho(ortho.id)}
                  title={isActive ? "Скрыть слой" : "Показать слой"}
                >
                  {isActive ? (
                    // Открытый глаз
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    </>
                  ) : (
                    // Закрытый глаз
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M1 1l22 22"></path>
                        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path>
                      </svg>
                    </>
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