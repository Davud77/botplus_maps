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

  const getGeometryBadgeClass = (geometryType: string) => {
    if (geometryType.includes('POLYGON')) return 'bg-polygon';
    if (geometryType.includes('LINE')) return 'bg-line';
    return 'bg-point';
  };

  return (
    <div className="table-container profile-vector-container">
      <div className="table-header profile-vector-header">
        <h3>Управление PostGIS (Local Docker)</h3>
        <div className="header-buttons">
          <button className="primary-button" onClick={handleCreateVectorDB}>
            + Создать БД
          </button>
          <button className="primary-button blue-btn" onClick={handleConnectVectorDB}>
            &#128279; Подключить БД
          </button>
        </div>
      </div>

      {loadingVector && <div className="status-message">Загрузка данных PostGIS...</div>}
      {errorVector && <div className="status-message error-message">{errorVector}</div>}

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
          <div key={db.id} className="section db-section">
            <div className="db-header">
              <div>
                <h4 className="db-title">🗄️ {db.name}</h4>
                <small className="db-subtitle">
                  Internal PostGIS • Status: <span className="status-active">Active</span>
                </small>
              </div>
              
              {creatingLayerInDb !== db.name && (
                <div className="db-actions">
                  <button className="primary-button small-btn" onClick={() => setCreatingLayerInDb(db.name)}>
                    + Новый слой
                  </button>
                  <button className="danger-button small-btn" onClick={() => alert('Отключение БД не реализовано')}>
                    Отключить
                  </button>
                </div>
              )}
            </div>

            {creatingLayerInDb === db.name && (
              <div className="create-layer-form">
                <h5>Создание новой таблицы (Слоя) в public</h5>
                <div className="form-controls">
                  <input 
                    type="text" 
                    placeholder="Имя таблицы (англ)" 
                    value={newLayerName} 
                    onChange={(e) => setNewLayerName(e.target.value)} 
                    className="form-input" 
                  />
                  <select 
                    value={newLayerType} 
                    onChange={(e) => setNewLayerType(e.target.value)} 
                    className="form-select"
                  >
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
              <div className="empty-db-message">База пуста</div>
            )}

            {sortedSchemas.map(schemaName => {
              const sortedLayers = layersBySchema[schemaName].sort((a, b) => a.tableName.localeCompare(b.tableName));
              return (
                <div key={schemaName} className="schema-section">
                  <div className="schema-header">
                    Схема: {schemaName}
                  </div>
                  <table className="data-table schema-table">
                    <thead>
                      <tr>
                        <th>Таблица</th>
                        <th>Тип геометрии</th>
                        <th>SRID</th>
                        <th>Объектов</th>
                        <th>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedLayers.map((layer) => (
                        <tr key={layer.id}>
                          <td><b>{layer.tableName}</b></td>
                          <td>
                            <span className={`geometry-badge ${getGeometryBadgeClass(layer.geometryType)}`}>
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