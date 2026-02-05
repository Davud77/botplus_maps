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
  deleteOrtho 
  // В будущем сюда добавить: fetchVectorDbs, createVectorDb, connectVectorDb
} from '../utils/api';

// --- Интерфейсы ---

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

// Новые интерфейсы для Вектора
interface VectorLayerItem {
  id: number;
  tableName: string;
  geometryType: 'POINT' | 'POLYGON' | 'LINESTRING' | 'UNKNOWN';
  featureCount: number;
}

interface VectorDbItem {
  id: number;
  name: string;
  host: string;
  port: number;
  status: 'connected' | 'error';
  layers: VectorLayerItem[]; // Вложенный список слоев
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

  // Загрузка векторных баз (MOCK DATA - Имитация)
  useEffect(() => {
    const loadVectorDbs = async () => {
      setLoadingVector(true);
      setErrorVector('');
      try {
        // TODO: Заменить на реальный вызов await fetchVectorDbs();
        // Имитация задержки сети
        await new Promise(resolve => setTimeout(resolve, 600));

        const mockData: VectorDbItem[] = [
          {
            id: 1,
            name: 'main_city_db',
            host: 'localhost',
            port: 5432,
            status: 'connected',
            layers: [
              { id: 101, tableName: 'buildings_polygon', geometryType: 'POLYGON', featureCount: 1250 },
              { id: 102, tableName: 'trees_point', geometryType: 'POINT', featureCount: 5000 },
            ]
          },
          {
            id: 2,
            name: 'external_project_db',
            host: '192.168.1.50',
            port: 5432,
            status: 'connected',
            layers: [
              { id: 201, tableName: 'roads_lines', geometryType: 'LINESTRING', featureCount: 340 }
            ]
          }
        ];
        setVectorDbs(mockData);
      } catch (error) {
        setErrorVector('Ошибка загрузки списка баз данных');
      } finally {
        setLoadingVector(false);
      }
    };

    if (activeTab === 'vector') {
      loadVectorDbs();
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

  // --- Методы для Вектора (Заглушки) ---

  const handleCreateVectorDB = async () => {
    const dbName = prompt('Введите название новой базы данных (PostGIS):');
    if (!dbName) return;

    try {
      // TODO: await createVectorDb({ name: dbName });
      alert(`Запрос на создание БД "${dbName}" отправлен (Logic pending)`);
      // После успеха обновить список setVectorDbs(...)
    } catch (error) {
      alert('Ошибка при создании БД');
    }
  };

  const handleConnectVectorDB = async () => {
    const connectionString = prompt('Введите строку подключения или Host (напр. 192.168.1.1):');
    if (!connectionString) return;

    try {
      // TODO: await connectExternalDb({ host: connectionString });
      alert(`Подключение к "${connectionString}" инициировано (Logic pending)`);
      // После успеха обновить список
    } catch (error) {
      alert('Ошибка подключения');
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

  // --- Новый рендер для вкладки Вектор ---
  const renderVector = () => (
    <div className="table-container">
      <div className="table-header" style={{ justifyContent: 'space-between' }}>
        <h3>Управление PostGIS</h3>
        <div style={{ display: 'flex', gap: '10px' }}>
          {/* Кнопка 1: Создать новую БД */}
          <button 
            className="primary-button" 
            onClick={handleCreateVectorDB}
          >
            + Создать БД
          </button>
          {/* Кнопка 2: Подключить существующую БД */}
          <button 
            className="primary-button" 
            style={{ backgroundColor: '#2196F3' }} // Отличаем цветом
            onClick={handleConnectVectorDB}
          >
            &#128279; Подключить БД
          </button>
        </div>
      </div>

      {loadingVector && <div style={{ padding: '20px' }}>Загрузка списка баз данных...</div>}
      {errorVector && <div style={{ color: 'red', padding: '20px' }}>{errorVector}</div>}

      {!loadingVector && !errorVector && vectorDbs.length === 0 && (
        <div className="empty-state">Нет подключенных баз данных</div>
      )}

      {/* Список баз данных */}
      {!loadingVector && !errorVector && vectorDbs.map((db) => (
        <div key={db.id} className="section" style={{ marginTop: '20px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '10px' }}>
            <div>
              <h4 style={{ margin: 0 }}>🗄️ {db.name}</h4>
              <small style={{ color: '#666' }}>Host: {db.host}:{db.port} • Status: <span style={{ color: 'green' }}>{db.status}</span></small>
            </div>
            <button className="danger-button" onClick={() => alert('Отключение БД не реализовано')}>Отключить</button>
          </div>

          {/* Список слоев внутри базы */}
          {db.layers.length === 0 ? (
            <div style={{ padding: '10px', color: '#888', fontStyle: 'italic' }}>Нет доступных слоев (таблиц)</div>
          ) : (
            <table className="data-table" style={{ marginTop: '0' }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Имя слоя (Table)</th>
                  <th>Тип геометрии</th>
                  <th>Объектов</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {db.layers.map((layer) => (
                  <tr key={layer.id}>
                    <td>{layer.id}</td>
                    <td><b>{layer.tableName}</b></td>
                    <td>
                      <span style={{ 
                        padding: '2px 6px', 
                        borderRadius: '4px', 
                        backgroundColor: layer.geometryType === 'POLYGON' ? '#e3f2fd' : '#e8f5e9',
                        fontSize: '0.85em'
                      }}>
                        {layer.geometryType}
                      </span>
                    </td>
                    <td>{layer.featureCount}</td>
                    <td>
                      <button className="icon-button" title="Просмотр на карте">👁️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );

  const renderPanoramas = () => (
    <div className="table-container">
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
    <div className="table-container">
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