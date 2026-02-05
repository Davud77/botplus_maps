// src/components/ProfilePage.tsx
import React, { FC, useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Header from './Header';
import { useAuth } from '../hooks/useAuth';
// Импортируем методы API
import { 
  fetchPanoramas, 
  fetchOrthophotos, 
  updatePanoTags, 
  deletePano, 
  deleteOrtho,
  // Векторные методы и типы
  fetchVectorDbs,
  createVectorDb,
  fetchVectorLayers,
  createVectorLayer,
  VectorDbItem,
  VectorLayerItem
} from '../utils/api';

// --- Локальные интерфейсы (для Панорам и Орто) ---

interface PanoItem {
  id: number;
  filename: string;
  latitude?: number;
  longitude?: number;
  tags?: string;
  upload_date?: string;
}

interface OrthoItem {
  id: number;
  filename: string;
  url: string;
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
}

interface AuthContextType {
  logout: () => void;
  user?: {
    email?: string;
    name?: string;
  };
}

const ProfilePage: FC = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth() as AuthContextType;

  const [activeTab, setActiveTab] = useState<'overview' | 'vector' | 'panoramas' | 'ortho' | 'dashboard'>('overview');

  // --- Панорамы ---
  const [panos, setPanos] = useState<PanoItem[]>([]);
  const [loadingPanos, setLoadingPanos] = useState(false);
  const [errorPanos, setErrorPanos] = useState('');

  const [editId, setEditId] = useState<number | null>(null);
  const [editTags, setEditTags] = useState<string>('');

  // --- Ортофотопланы ---
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState('');

  // --- Векторные данные (PostGIS) ---
  const [vectorDbs, setVectorDbs] = useState<VectorDbItem[]>([]);
  const [loadingVector, setLoadingVector] = useState(false);
  const [errorVector, setErrorVector] = useState('');

  // Состояние для формы создания нового слоя
  const [creatingLayerInDb, setCreatingLayerInDb] = useState<string | null>(null); // ID/Name базы, где открыта форма
  const [newLayerName, setNewLayerName] = useState('');
  const [newLayerType, setNewLayerType] = useState('POINT');

  // -------------------------------------------------------------------------
  //                               ЗАГРУЗКА ДАННЫХ
  // -------------------------------------------------------------------------
  
  // Загрузка панорам
  useEffect(() => {
    const loadPanoramas = async () => {
      setLoadingPanos(true);
      setErrorPanos('');
      try {
        const data: PanoItem[] = await fetchPanoramas();
        setPanos(data);
      } catch (error) {
        if (error instanceof Error) {
          setErrorPanos(error.message);
        } else {
          setErrorPanos('Неизвестная ошибка при загрузке панорам');
        }
      } finally {
        setLoadingPanos(false);
      }
    };

    if (activeTab === 'panoramas') {
      loadPanoramas();
    }
  }, [activeTab]);

  // Загрузка ортофотопланов
  useEffect(() => {
    const loadOrthos = async () => {
      setLoadingOrthos(true);
      setErrorOrthos('');
      try {
        const data: OrthoItem[] = await fetchOrthophotos();
        setOrthos(data);
      } catch (error) {
        if (error instanceof Error) {
          setErrorOrthos(error.message);
        } else {
          setErrorOrthos('Неизвестная ошибка при загрузке ортофотопланов');
        }
      } finally {
        setLoadingOrthos(false);
      }
    };

    if (activeTab === 'ortho') {
      loadOrthos();
    }
  }, [activeTab]);

  // Загрузка векторных баз
  const loadVectorData = async () => {
    setLoadingVector(true);
    setErrorVector('');
    try {
      // 1. Получаем список подключенных баз
      const dbs = await fetchVectorDbs();
      
      // Сортировка баз по алфавиту
      dbs.sort((a, b) => a.name.localeCompare(b.name));

      // 2. Для каждой базы подгружаем список слоев (параллельно)
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
    if (activeTab === 'vector') {
      loadVectorData();
    }
  }, [activeTab]);

  // -------------------------------------------------------------------------
  //                           ОБРАБОТЧИКИ ДЕЙСТВИЙ
  // -------------------------------------------------------------------------

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // --- Редактирование тегов (панорамы) ---
  const handleEdit = (panoId: number, currentTags: string = '') => {
    setEditId(panoId);
    setEditTags(currentTags);
  };

  const handleSaveTags = async (panoId: number) => {
    try {
      await updatePanoTags(panoId, editTags);
      setPanos((prev) =>
        prev.map((p) => (p.id === panoId ? { ...p, tags: editTags } : p))
      );
      alert('Теги сохранены!');
      setEditId(null);
      setEditTags('');
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка');
    }
  };

  const handleDelete = async (panoId: number) => {
    if (!window.confirm('Уверены, что хотите удалить панораму?')) return;
    try {
      await deletePano(panoId);
      setPanos((prev) => prev.filter((p) => p.id !== panoId));
      alert('Панорама удалена!');
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка');
    }
  };

  const handleDeleteOrtho = async (orthoId: number) => {
    if (!window.confirm('Удалить ортофотоплан?')) return;
    try {
      await deleteOrtho(orthoId);
      setOrthos((prev) => prev.filter((o) => o.id !== orthoId));
      alert('Ортофотоплан удалён!');
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка');
    }
  };

  // --- Методы для Вектора ---

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
      // Блокируем интерфейс легкой загрузкой или просто ждем
      await createVectorLayer(dbName, newLayerName, newLayerType);
      
      alert('Слой успешно создан!');
      
      // Сброс формы
      setCreatingLayerInDb(null);
      setNewLayerName('');
      setNewLayerType('POINT');
      
      // Обновляем данные
      await loadVectorData();
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка создания слоя');
    }
  };

  // -------------------------------------------------------------------------
  //                           РЕНДЕР КОНТЕНТА ТАБОв
  // -------------------------------------------------------------------------

  const renderOverview = () => (
    <div className="overview-content">
      <div className="profile-sidebar">
        <div className="user-avatar">
          <svg width="120" height="120" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M12 12q-1.65 0-2.825-1.175T8 8q0-1.65 1.175-2.825T12 4q1.65 0 2.825 1.175T16 8q0 1.65-1.175 2.825T12 12Zm-8 8v-2.8q0-.85.438-1.563T5.6 14.55q1.55-.775 3.15-1.163T12 13q1.65 0 3.25.388t3.15 1.162q.725.375 1.163 1.088T20 17.2V20H4Z"
            />
          </svg>
        </div>
        <button className="logout-button" onClick={handleLogout}>
          Выйти
        </button>
      </div>

      <div className="profile-main-content">
        <div className="section">
          <h3>Основная информация</h3>
          <div className="info-grid">
            <div className="info-label">Email</div>
            <div className="info-value">{user?.email || 'example@gmail.com'}</div>
            <div className="info-label">Полное имя</div>
            <div className="info-value">{user?.name || 'Davud'}</div>
            <div className="info-label">Имя</div>
            <div className="info-value">Davud</div>
            <div className="info-label">Логин</div>
            <div className="info-value">davud</div>
          </div>
        </div>

        <div className="section">
          <h3>Последние действия</h3>
          <div className="activity-list">
            <div className="activity-item">
              <div className="activity-date">2024-02-15 14:30</div>
              <div className="activity-text">Загружена панорама "city_center_01"</div>
            </div>
            <div className="activity-item">
              <div className="activity-date">2024-02-14 09:15</div>
              <div className="activity-text">Обновлены теги для панорамы #1245</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // --- Рендер вкладки Вектор (Обновленная группировка) ---
  const renderVector = () => (
    <div 
      className="table-container" 
      style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }} // <-- Добавлен скролл
    >
      <div className="table-header" style={{ justifyContent: 'space-between' }}>
        <h3>Управление PostGIS (Local Docker)</h3>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="primary-button" onClick={handleCreateVectorDB}>
            + Создать БД
          </button>
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

      {/* Перебираем Базы Данных */}
      {!loadingVector && !errorVector && vectorDbs.map((db) => {
        // Группировка слоев по Схемам (schema)
        const layersBySchema: { [key: string]: VectorLayerItem[] } = {};
        
        if (db.layers) {
          db.layers.forEach(layer => {
            const schema = layer.schema || 'public'; // fallback если схемы нет
            if (!layersBySchema[schema]) {
              layersBySchema[schema] = [];
            }
            layersBySchema[schema].push(layer);
          });
        }

        // Сортируем схемы по алфавиту
        const sortedSchemas = Object.keys(layersBySchema).sort();

        return (
          <div key={db.id} className="section" style={{ marginTop: '20px', marginBottom: '20px' }}>
            
            {/* Карточка БД */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '10px' }}>
              <div>
                <h4 style={{ margin: 0 }}>🗄️ {db.name}</h4>
                <small style={{ color: '#666' }}>Internal PostGIS • Status: <span style={{ color: 'green' }}>Active</span></small>
              </div>
              
              {/* Кнопка создания слоя */}
              {creatingLayerInDb !== db.name && (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button 
                    className="primary-button" 
                    style={{ fontSize: '0.8em', padding: '5px 10px' }}
                    onClick={() => setCreatingLayerInDb(db.name)}
                  >
                    + Новый слой
                  </button>
                  <button className="danger-button" style={{ fontSize: '0.8em' }} onClick={() => alert('Отключение БД не реализовано')}>
                    Отключить
                  </button>
                </div>
              )}
            </div>

            {/* Форма создания нового слоя */}
            {creatingLayerInDb === db.name && (
              <div style={{ background: '#f5f5f5', padding: '15px', borderRadius: '4px', marginBottom: '15px', border: '1px solid #ddd' }}>
                <h5>Создание новой таблицы (Слоя) в public</h5>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <input 
                    type="text" 
                    placeholder="Имя таблицы (англ)" 
                    value={newLayerName}
                    onChange={(e) => setNewLayerName(e.target.value)}
                    style={{ padding: '8px', flex: 1, border: '1px solid #ccc', borderRadius: '4px' }}
                  />
                  <select 
                    value={newLayerType} 
                    onChange={(e) => setNewLayerType(e.target.value)}
                    style={{ padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
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

            {/* Если слоев нет */}
            {sortedSchemas.length === 0 && (
              <div style={{ padding: '10px', color: '#888', fontStyle: 'italic', fontSize: '0.9em' }}>
                База пуста (нет таблиц в geometry_columns)
              </div>
            )}

            {/* Перебираем Схемы */}
            {sortedSchemas.map(schemaName => {
              // Сортируем таблицы внутри схемы по алфавиту
              const sortedLayers = layersBySchema[schemaName].sort((a, b) => a.tableName.localeCompare(b.tableName));

              return (
                <div key={schemaName} style={{ marginBottom: '15px' }}>
                  <div style={{ 
                    padding: '5px 10px', 
                    backgroundColor: '#eef2f5', 
                    borderLeft: '4px solid #2196F3', 
                    marginBottom: '5px',
                    fontWeight: 'bold',
                    fontSize: '0.9em',
                    color: '#444'
                  }}>
                    Схема: {schemaName}
                  </div>

                  <table className="data-table" style={{ marginTop: '0', marginLeft: '10px', width: 'calc(100% - 10px)' }}>
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
                            <span style={{ 
                              padding: '2px 6px', 
                              borderRadius: '4px', 
                              backgroundColor: layer.geometryType.includes('POLYGON') ? '#e3f2fd' : 
                                               layer.geometryType.includes('LINE') ? '#fff3e0' : '#e8f5e9',
                              fontSize: '0.85em'
                            }}>
                              {layer.geometryType}
                            </span>
                          </td>
                          <td>{layer.srid}</td>
                          <td>{layer.featureCount}</td>
                          <td>
                            <button className="icon-button" title="Просмотр">👁️</button>
                          </td>
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

  const renderPanoramas = () => (
    <div 
      className="table-container"
      style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }} // <-- Добавлен скролл
    >
      <div className="table-header">
        <h3>Мои панорамы</h3>
        <Link to="/upload">
          <button className="primary-button">+ Загрузить панораму</button>
        </Link>
      </div>

      {loadingPanos && <div>Загрузка панорам...</div>}
      {errorPanos && <div style={{ color: 'red' }}>{errorPanos}</div>}

      {!loadingPanos && !errorPanos && panos.length === 0 && (
        <div className="empty-state">Нет загруженных панорам</div>
      )}

      {!loadingPanos && !errorPanos && panos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Файл</th>
              <th>Теги</th>
              <th>Координаты</th>
              <th>Дата загрузки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {panos.map((pano) => (
              <tr key={pano.id}>
                <td>{pano.id}</td>
                <td>{pano.filename}</td>
                <td>
                  {editId === pano.id ? (
                    <input
                      type="text"
                      value={editTags}
                      onChange={(e) => setEditTags(e.target.value)}
                      className="tags-input"
                    />
                  ) : (
                    pano.tags || 'Нет тегов'
                  )}
                </td>
                <td>
                  {pano.latitude && pano.longitude
                    ? `${pano.latitude.toFixed(5)}, ${pano.longitude.toFixed(5)}`
                    : 'N/A'}
                </td>
                <td>
                  {pano.upload_date
                    ? new Date(pano.upload_date).toLocaleDateString()
                    : '—'}
                </td>
                <td>
                  <div className="actions-group">
                    {editId === pano.id ? (
                      <button
                        className="success-button"
                        onClick={() => handleSaveTags(pano.id)}
                      >
                        &#10003;
                      </button>
                    ) : (
                      <button
                        className="icon-button"
                        onClick={() => handleEdit(pano.id, pano.tags || '')}
                      >
                        ✎
                      </button>
                    )}

                    <button
                      className="danger-button"
                      onClick={() => handleDelete(pano.id)}
                    >
                      &times;
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  const renderOrtho = () => (
    <div 
      className="table-container"
      style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }} // <-- Добавлен скролл
    >
      <div className="table-header">
        <h3>Ортофотопланы</h3>
        <Link to="/uploadortho">
          <button className="primary-button">+ Загрузить ортофотоплан</button>
        </Link>
      </div>

      {loadingOrthos && <div>Загрузка ортофотопланов...</div>}
      {errorOrthos && <div style={{ color: 'red' }}>{errorOrthos}</div>}

      {!loadingOrthos && !errorOrthos && orthos.length === 0 && (
        <div className="empty-state">Нет загруженных ортофотопланов</div>
      )}

      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Превью</th>
              <th>Границы (W,S,E,N)</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {orthos.map((ortho) => (
              <tr key={ortho.id}>
                <td>{ortho.filename}</td>
                <td>
                  <img
                    src={ortho.url}
                    alt="preview"
                    style={{ width: '100px', border: '1px solid #ccc' }}
                  />
                </td>
                <td>
                  {ortho.bounds
                    ? `${ortho.bounds.west}, ${ortho.bounds.south}, ${ortho.bounds.east}, ${ortho.bounds.north}`
                    : 'Нет данных'}
                </td>
                <td>
                  <div className="actions-group">
                    <button
                      className="icon-button"
                      onClick={() => window.open(ortho.url, '_blank')}
                    >
                      &darr;
                    </button>
                    <button
                      className="danger-button"
                      onClick={() => handleDeleteOrtho(ortho.id)}
                    >
                      &times;
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  const renderDashboard = () => (
    <div className="development-notice">
      <h2>🚧 Страница в разработке</h2>
      <p>Мы активно работаем над этим разделом</p>
    </div>
  );

  // -------------------------------------------------------------------------
  //                                РЕНДЕР
  // -------------------------------------------------------------------------
  
  return (
    <div className="background">
      <Header />
      <div className="profile-page">
        <div className="navigation-tabs">
          <button
            className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Обзор
          </button>
          <button
            className={`tab-button ${activeTab === 'vector' ? 'active' : ''}`}
            onClick={() => setActiveTab('vector')}
          >
            Вектор
          </button>
          <button
            className={`tab-button ${activeTab === 'panoramas' ? 'active' : ''}`}
            onClick={() => setActiveTab('panoramas')}
          >
            Панорамы
          </button>
          <button
            className={`tab-button ${activeTab === 'ortho' ? 'active' : ''}`}
            onClick={() => setActiveTab('ortho')}
          >
            Ортофотопланы
          </button>
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Дашборд
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'vector' && renderVector()}
          {activeTab === 'panoramas' && renderPanoramas()}
          {activeTab === 'ortho' && renderOrtho()}
          {activeTab === 'dashboard' && renderDashboard()}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;