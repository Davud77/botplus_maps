import React, { useEffect } from 'react';
import { BasePanel } from './BasePanel';
import { useMapStore } from '../../hooks/useMapStore';
import L from 'leaflet'; // Импортируем типы Leaflet

interface OrthoPanelProps {
  onClose: () => void;
  map: L.Map | null; // Добавляем проп для карты
}

export const OrthoPanel: React.FC<OrthoPanelProps> = ({ onClose, map }) => {
  const { orthoImages, selectedOrthoIds, isLoadingOrtho, fetchOrthos, toggleOrtho, fitToBounds } = useMapStore();

  useEffect(() => {
    fetchOrthos();
  }, []);

  return (
    <BasePanel title="Ортофотопланы" onClose={onClose}>
      {isLoadingOrtho && <div style={{textAlign:'center', color:'#888'}}>Загрузка списка...</div>}
      
      {!isLoadingOrtho && orthoImages.length === 0 && (
        <div style={{textAlign:'center', color:'#ccc'}}>Список пуст</div>
      )}

      {orthoImages.map(ortho => {
        const isActive = selectedOrthoIds.includes(ortho.id);
        
        return (
          <div key={ortho.id} className={`ortho-item ${isActive ? 'active' : ''}`}>
            <div className="ortho-info">
              <div className="ortho-title">{ortho.filename}</div>
              {/* Кнопка "Найти на карте" */}
              <button 
                className="zoom-btn"
                onClick={(e) => { 
                  e.stopPropagation(); 
                  // Проверяем, существует ли карта перед вызовом
                  if (map) {
                    fitToBounds(ortho.id, map); 
                  } else {
                    console.warn("Map instance is not ready");
                  }
                }}
                title="Показать на карте"
                disabled={!map} // Блокируем кнопку, если карта не прогрузилась
              >
                🔍
              </button>
            </div>
            
            <label className="toggle-switch">
              <input 
                type="checkbox" 
                checked={isActive} 
                onChange={() => toggleOrtho(ortho.id)} 
              />
              <span className="slider round"></span>
            </label>
          </div>
        );
      })}

      <style>{`
        .ortho-item {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px; background: #f9f9f9; border-radius: 6px; margin-bottom: 8px;
          border: 1px solid #eee;
        }
        .ortho-item.active { background: #e3f2fd; border-color: #bbdefb; }
        .ortho-title { font-size: 13px; font-weight: 500; word-break: break-all; margin-right: 10px;}
        .ortho-info { flex: 1; display: flex; align-items: center; gap: 8px; }
        .zoom-btn { border: none; background: none; cursor: pointer; font-size: 14px; opacity: 0.6; }
        .zoom-btn:hover { opacity: 1; transform: scale(1.1); }

        /* Toggle Switch CSS */
        .toggle-switch { position: relative; display: inline-block; width: 34px; height: 20px; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #2196F3; }
        input:checked + .slider:before { transform: translateX(14px); }
      `}</style>
    </BasePanel>
  );
};