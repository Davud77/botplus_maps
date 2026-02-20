// src/components/maps/ui/panels/VectorPanel.tsx
import React, { useEffect, useState } from 'react';
import { BasePanel } from './BasePanel';
import { useVectorStore } from '../../hooks/useVectorStore';
import { fetchVectorDbs, fetchVectorLayers, VectorLayerItem } from '../../../../utils/api';


interface VectorGroup {
  dbName: string;
  layers: VectorLayerItem[];
}

// Тип для выбранного слоя, чтобы знать контекст действий
interface SelectedLayerInfo extends VectorLayerItem {
  dbName: string;
  uniqueId: string;
}

export const VectorPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { activeVectorIds, loadingLayerId, toggleLayer } = useVectorStore();
  const [groups, setGroups] = useState<VectorGroup[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Состояние выбранного слоя (для активации панели действий)
  const [selectedLayer, setSelectedLayer] = useState<SelectedLayerInfo | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const dbs = await fetchVectorDbs();
        dbs.sort((a, b) => a.name.localeCompare(b.name));
        const res: VectorGroup[] = [];
        
        for (const db of dbs) {
          try {
            const layers = await fetchVectorLayers(db.name);
            if (layers.length) {
                res.push({ dbName: db.name, layers });
            }
          } catch (e) { 
            console.warn(`Error loading layers for ${db.name}`, e); 
          }
        }
        setGroups(res);
      } catch (err) {
        console.error("Failed to load vector DBs", err);
      } finally { 
        setLoading(false); 
      }
    };
    load();
  }, []);

  // Обработчик выбора слоя (клик по строке)
  const handleSelectLayer = (dbName: string, layer: VectorLayerItem) => {
    const uniqueId = `${dbName}-${layer.schema}-${layer.tableName}`;
    setSelectedLayer({ ...layer, dbName, uniqueId });
  };

  // --- Компонент кнопки действия ---
  const ActionButton = ({ 
    icon, label, onClick, disabled 
  }: { icon: React.ReactNode, label: string, onClick?: () => void, disabled: boolean }) => (
    <button 
      className="action-btn"
      onClick={onClick}
      disabled={disabled}
      title={label}
    >
      <div className="action-btn-icon">{icon}</div>
    </button>
  );

  return (
    <BasePanel title="Векторные слои" onClose={onClose}>
      
      {/* 1. ПАНЕЛЬ ДЕЙСТВИЙ (Panel Actions) */}
      <div className="vector-panel-actions">
        <div className="action-buttons-row">
            {/* Таблица */}
            <ActionButton 
              disabled={!selectedLayer} 
              label="Таблица объектов"
              onClick={() => console.log("Open Table", selectedLayer)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M4 14h4v-4H4v4zm0 5h4v-4H4v4zM4 9h4V5H4v4zm5 5h12v-4H9v4zm0 5h12v-4H9v4zM9 5v4h12V5H9z"/></svg>
              } 
            />
            {/* Фильтр */}
            <ActionButton 
              disabled={!selectedLayer} 
              label="Фильтр"
              onClick={() => console.log("Open Filter", selectedLayer)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/></svg>
              } 
            />
            {/* Zoom to layer */}
            <ActionButton 
              disabled={!selectedLayer} 
              label="Увеличить до слоя"
              onClick={() => console.log("Zoom to layer", selectedLayer)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM12 8h-2v3h-3v2h3v3h2v-3h3v-2h-3z"/></svg>
              } 
            />
            {/* Непрозрачность */}
            <ActionButton 
              disabled={!selectedLayer} 
              label="Непрозрачность"
              onClick={() => console.log("Opacity", selectedLayer)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.66 8L12 2.35 6.34 8C4.78 9.56 4 11.64 4 13.64s.78 4.11 2.34 5.67 3.61 2.35 5.66 2.35 4.1-.79 5.66-2.35S20 15.64 20 13.64 19.22 9.56 17.66 8zM6 14c.01-2 .62-3.27 1.76-4.4L12 5.27l4.24 4.38C17.38 10.77 17.99 12 18 14H6z"/></svg>
              } 
            />
             {/* Стили */}
             <ActionButton 
              disabled={!selectedLayer} 
              label="Стилизация"
              onClick={() => console.log("Styles", selectedLayer)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a9 9 0 0 0 0 18c4.97 0 9-4.03 9-9s-4.03-9-9-9zM7 10.5c-.83 0-1.5-.67-1.5-1.5S6.17 7.5 7 7.5s1.5.67 1.5 1.5S7.83 10.5 7 10.5zm3.5 3.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm5 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm2.5-3.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>
              } 
            />
        </div>
        
        {/* Индикатор выбранного слоя */}
        <div className="vector-panel-selected-layer">
           {selectedLayer ? (
               selectedLayer.tableName.length > 10 
                 ? selectedLayer.tableName.slice(0, 10) + '...' 
                 : selectedLayer.tableName
           ) : 'Выберите слой'}
        </div>
      </div>

      {/* 2. СПИСОК СЛОЕВ (Scrollable) */}
      <div className="vector-panel-content">
        {loading && <div className="vector-panel-message">Загрузка...</div>}
        
        {!loading && groups.length === 0 && (
          <div className="vector-panel-message">Нет доступных слоев</div>
        )}
        
        {groups.map(group => {
          const bySchema: Record<string, VectorLayerItem[]> = {};
          group.layers.forEach(l => {
            const s = l.schema || 'public';
            if (!bySchema[s]) bySchema[s] = [];
            bySchema[s].push(l);
          });
          const schemas = Object.keys(bySchema).sort();

          return (
            <div className="vector-group-container" key={group.dbName}>
              <div className="vector-panel-group-header"> {group.dbName}</div>
              
              {schemas.map(schema => (
                <div key={schema} className="vector-schema-container">
                  <div className="vector-panel-schema-header">
                    {schema}
                  </div>
                  
                  {bySchema[schema].sort((a,b) => a.tableName.localeCompare(b.tableName)).map(layer => {
                     const id = `${group.dbName}-${layer.schema}-${layer.tableName}`;
                     const isActive = activeVectorIds.has(id);
                     const isLoad = loadingLayerId === id;
                     const isSelected = selectedLayer?.uniqueId === id;
                     
                     return (
                       <div 
                        key={layer.id} 
                        onClick={() => handleSelectLayer(group.dbName, layer)}
                        className={`layer-item ${isSelected ? 'selected' : ''}`}
                       >
                         <span 
                           title={layer.tableName}
                           className={`layer-name ${isSelected ? 'selected' : (isActive ? 'active' : '')}`}
                         >
                           {/* Ограничиваем длину названия до 30 символов + троеточие */}
                           {layer.tableName.length > 10 
                             ? `${layer.tableName.slice(0, 30)}...` 
                             : layer.tableName}
                         </span>
                         
                         <button 
                           onClick={(e) => {
                               e.stopPropagation();
                               toggleLayer(group.dbName, layer);
                           }}
                           disabled={isLoad}
                           className="layer-toggle-btn"
                           title={isActive ? "Скрыть слой" : "Показать слой"}
                         >
                           {isLoad ? (
                              <div className="spinner-mini" />
                           ) : isActive ? (
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" fill="#2196F3"/>
                              </svg>
                           ) : (
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                 <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z" fill="#ccc"/>
                              </svg>
                           )}
                         </button>
                       </div>
                     )
                  })}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </BasePanel>
  );
};