import React, { FC, useEffect, useState } from 'react';
import { 
  fetchVectorDbs, 
  fetchVectorLayers, 
  createVectorDb, 
  createVectorLayer,
  VectorDbItem,
  VectorLayerItem
} from '../../utils/api'; 

const ProfileVector: FC = () => {
  const [vectorDbs, setVectorDbs] = useState<VectorDbItem[]>([]);
  const [loadingVector, setLoadingVector] = useState(false);
  const [errorVector, setErrorVector] = useState('');

  // Состояние для формы создания нового слоя
  const [creatingLayerInDb, setCreatingLayerInDb] = useState<string | null>(null);
  const [newLayerName, setNewLayerName] = useState('');
  const [newLayerType, setNewLayerType] = useState('POINT');

  const loadVectorData = async () => {
    setLoadingVector(true);
    setErrorVector('');
    try {
      const dbs = await fetchVectorDbs();
      dbs.sort((a, b) => a.name.localeCompare(b.name));

      const dbsWithLayers = await Promise.all(dbs.map(async (db) => {
        try {
          const layers = await fetchVectorLayers(db.name);
          return { ...db, layers: layers };
        } catch (err) {
          console.warn(`Could not load layers for ${db.name}`, err);
          return { ...db, layers: [] };
        }
      }));

      setVectorDbs(dbsWithLayers);
    } catch (error) {
      if (error instanceof Error) {
        setErrorVector(error.message);
      } else {
        setErrorVector('Ошибка соединения с сервером PostGIS');
      }
    } finally {
      setLoadingVector(false);
    }
  };

  useEffect(() => {
    loadVectorData();
  }, []);

  const handleCreateVectorDB = async () => {
    const dbName = prompt('Введите название новой базы данных (латиница, без пробелов):');
    if (!dbName) return;

    try {
      setLoadingVector(true);
      await createVectorDb(dbName);
      alert(`База данных "${dbName}" успешно создана!`);
      await loadVectorData(); 
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка при создании БД');
      setLoadingVector(false);
    }
  };

  const handleConnectVectorDB = async () => {
    alert('Подключение внешних (удаленных) PostGIS баз будет реализовано позже.');
  };

  const handleCreateLayer = async (dbName: string) => {
    if (!newLayerName) {
      alert('Введите имя таблицы');
      return;
    }
    try {
      await createVectorLayer(dbName, newLayerName, newLayerType);
      alert('Слой успешно создан!');
      setCreatingLayerInDb(null);
      setNewLayerName('');
      setNewLayerType('POINT');
      await loadVectorData();
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка создания слоя');
    }
  };

  return (
    <div className="table-container" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
      <div className="table-header" style={{ justifyContent: 'space-between' }}>
        <h3>Управление PostGIS (Local Docker)</h3>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="primary-button" onClick={handleCreateVectorDB}>+ Создать БД</button>
          <button className="primary-button" style={{ backgroundColor: '#2196F3' }} onClick={handleConnectVectorDB}>
            &#128279; Подключить БД
          </button>
        </div>
      </div>

      {loadingVector && <div style={{ padding: '20px' }}>Загрузка данных PostGIS...</div>}
      {errorVector && <div style={{ color: 'red', padding: '20px' }}>{errorVector}</div>}

      {!loadingVector && !errorVector && vectorDbs.length === 0 && (
        <div className="empty-state">Нет доступных баз данных</div>
      )}

      {!loadingVector && !errorVector && vectorDbs.map((db) => {
        const layersBySchema: { [key: string]: VectorLayerItem[] } = {};
        if (db.layers) {
          db.layers.forEach(layer => {
            const schema = layer.schema || 'public';
            if (!layersBySchema[schema]) layersBySchema[schema] = [];
            layersBySchema[schema].push(layer);
          });
        }
        const sortedSchemas = Object.keys(layersBySchema).sort();

        return (
          <div key={db.id} className="section" style={{ marginTop: '20px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '10px' }}>
              <div>
                <h4 style={{ margin: 0 }}>🗄️ {db.name}</h4>
                <small style={{ color: '#666' }}>Internal PostGIS • Status: <span style={{ color: 'green' }}>Active</span></small>
              </div>
              
              {creatingLayerInDb !== db.name && (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button className="primary-button" style={{ fontSize: '0.8em', padding: '5px 10px' }} onClick={() => setCreatingLayerInDb(db.name)}>
                    + Новый слой
                  </button>
                  <button className="danger-button" style={{ fontSize: '0.8em' }} onClick={() => alert('Отключение БД не реализовано')}>
                    Отключить
                  </button>
                </div>
              )}
            </div>

            {creatingLayerInDb === db.name && (
              <div style={{ background: '#f5f5f5', padding: '15px', borderRadius: '4px', marginBottom: '15px', border: '1px solid #ddd' }}>
                <h5>Создание новой таблицы (Слоя) в public</h5>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <input type="text" placeholder="Имя таблицы (англ)" value={newLayerName} onChange={(e) => setNewLayerName(e.target.value)} style={{ padding: '8px', flex: 1, border: '1px solid #ccc', borderRadius: '4px' }} />
                  <select value={newLayerType} onChange={(e) => setNewLayerType(e.target.value)} style={{ padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}>
                    <option value="POINT">Точки (POINT)</option>
                    <option value="LINESTRING">Линии (LINESTRING)</option>
                    <option value="POLYGON">Полигоны (POLYGON)</option>
                  </select>
                  <button className="success-button" onClick={() => handleCreateLayer(db.name)}>Создать</button>
                  <button className="danger-button" onClick={() => { setCreatingLayerInDb(null); setNewLayerName(''); }}>Отмена</button>
                </div>
              </div>
            )}

            {sortedSchemas.length === 0 && (
              <div style={{ padding: '10px', color: '#888', fontStyle: 'italic', fontSize: '0.9em' }}>База пуста</div>
            )}

            {sortedSchemas.map(schemaName => {
              const sortedLayers = layersBySchema[schemaName].sort((a, b) => a.tableName.localeCompare(b.tableName));
              return (
                <div key={schemaName} style={{ marginBottom: '15px' }}>
                  <div style={{ padding: '5px 10px', backgroundColor: '#eef2f5', borderLeft: '4px solid #2196F3', marginBottom: '5px', fontWeight: 'bold', fontSize: '0.9em', color: '#444' }}>
                    Схема: {schemaName}
                  </div>
                  <table className="data-table" style={{ marginTop: '0', marginLeft: '10px', width: 'calc(100% - 10px)' }}>
                    <thead>
                      <tr><th>Таблица</th><th>Тип геометрии</th><th>SRID</th><th>Объектов</th><th>Действия</th></tr>
                    </thead>
                    <tbody>
                      {sortedLayers.map((layer) => (
                        <tr key={layer.id}>
                          <td><b>{layer.tableName}</b></td>
                          <td>
                            <span style={{ padding: '2px 6px', borderRadius: '4px', backgroundColor: layer.geometryType.includes('POLYGON') ? '#e3f2fd' : layer.geometryType.includes('LINE') ? '#fff3e0' : '#e8f5e9', fontSize: '0.85em' }}>
                              {layer.geometryType}
                            </span>
                          </td>
                          <td>{layer.srid}</td>
                          <td>{layer.featureCount}</td>
                          <td><button className="icon-button" title="Просмотр">👁️</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export default ProfileVector;