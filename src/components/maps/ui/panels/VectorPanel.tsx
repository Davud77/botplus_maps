// src/components/maps/ui/panels/VectorPanel.tsx
import React, { useEffect, useState } from 'react';
import { BasePanel } from './BasePanel';
import { useVectorStore } from '../../hooks/useVectorStore';
// ИСПРАВЛЕНИЕ: Добавлен еще один уровень "../" 
import { fetchVectorDbs, fetchVectorLayers, VectorLayerItem } from '../../../../utils/api';

interface VectorGroup {
  dbName: string;
  layers: VectorLayerItem[];
}

export const VectorPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { activeVectorIds, loadingLayerId, toggleLayer } = useVectorStore();
  const [groups, setGroups] = useState<VectorGroup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const dbs = await fetchVectorDbs();
        // Сортировка баз
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

  return (
    <BasePanel title="Векторные слои" onClose={onClose}>
      {loading && <div style={{textAlign:'center', color:'#888', padding: '20px'}}>Загрузка...</div>}
      
      {!loading && groups.length === 0 && (
        <div style={{textAlign:'center', color:'#999', padding: '20px'}}>Нет доступных слоев</div>
      )}
      
      {groups.map(group => {
        // Группировка слоев по схемам внутри базы
        const bySchema: Record<string, VectorLayerItem[]> = {};
        group.layers.forEach(l => {
          const s = l.schema || 'public';
          if (!bySchema[s]) bySchema[s] = [];
          bySchema[s].push(l);
        });
        const schemas = Object.keys(bySchema).sort();

        return (
          <div key={group.dbName} style={{ marginBottom: 12 }}>
            <div style={{ 
                background: '#f5f5f5', 
                padding: '6px 8px', 
                borderRadius: 4, 
                fontWeight: 'bold', 
                fontSize: 13,
                color: '#444',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
            }}>
              <span>🗄️</span> {group.dbName}
            </div>
            
            {schemas.map(schema => (
              <div key={schema} style={{ marginLeft: 8, borderLeft: '2px solid #eee', paddingLeft: 8, marginTop: 6 }}>
                <div style={{ fontSize: 11, color: '#2196F3', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: 4 }}>
                  {schema}
                </div>
                
                {bySchema[schema].sort((a,b) => a.tableName.localeCompare(b.tableName)).map(layer => {
                   const id = `${group.dbName}-${layer.schema}-${layer.tableName}`;
                   const isActive = activeVectorIds.has(id);
                   const isLoad = loadingLayerId === id;
                   
                   return (
                     <div key={layer.id} style={{ 
                         display: 'flex', 
                         justifyContent: 'space-between', 
                         alignItems: 'center', 
                         padding: '4px 0',
                         fontSize: 13
                     }}>
                       <span style={{ color: isActive ? '#000' : '#555' }}>
                         {layer.tableName}
                       </span>
                       
                       <button 
                         onClick={() => toggleLayer(group.dbName, layer)}
                         disabled={isLoad}
                         style={{ 
                             border: 'none', 
                             background: 'none', 
                             cursor: isLoad ? 'wait' : 'pointer',
                             padding: '2px 6px'
                         }}
                         title={isActive ? "Скрыть слой" : "Показать слой"}
                       >
                         {isLoad ? (
                            <div className="spinner-mini" />
                         ) : isActive ? (
                            // Иконка "Глаз открыт" (Синий)
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" fill="#2196F3"/>
                            </svg>
                         ) : (
                            // Иконка "Глаз закрыт/Офф" (Серый)
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
      
      <style>{`
        .spinner-mini {
          width: 14px; height: 14px;
          border: 2px solid #ccc;
          border-top-color: #2196F3;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        @keyframes spin { from {transform: rotate(0deg);} to {transform: rotate(360deg);} }
      `}</style>
    </BasePanel>
  );
};