// src/components/profile/ProfileOrthophotos.tsx
import React, { FC, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
// [REF] Импортируем типы из api.ts, чтобы использовать единый источник истины
import { fetchOrthophotos, deleteOrtho, OrthoItem } from '../../utils/api';

const ProfileOrthophotos: FC = () => {
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState('');

  const loadOrthos = async () => {
    setLoadingOrthos(true);
    setErrorOrthos('');
    try {
      const data = await fetchOrthophotos();
      
      // Проверяем, что пришел массив, а не HTML (в случае ошибки 404/500)
      if (Array.isArray(data)) {
        setOrthos(data);
      } else {
        throw new Error('Получены некорректные данные. Ожидался массив JSON.');
      }
    } catch (error) {
      console.error("Ошибка загрузки ортофотопланов:", error);
      setErrorOrthos(error instanceof Error ? error.message : 'Ошибка при загрузке');
    } finally {
      setLoadingOrthos(false);
    }
  };

  useEffect(() => {
    loadOrthos();
  }, []);

  const handleDeleteOrtho = async (orthoId: number) => {
    if (!window.confirm('Удалить этот ортофотоплан?')) return;
    try {
      await deleteOrtho(orthoId);
      setOrthos((prev) => prev.filter((o) => o.id !== orthoId));
      alert('Ортофотоплан успешно удалён!');
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка удаления');
    }
  };

  return (
    <div className="table-container" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
      <div className="table-header" style={{ justifyContent: 'space-between' }}>
        <h3>Ортофотопланы</h3>
        <Link to="/uploadortho">
          <button className="primary-button">+ Загрузить ортофотоплан</button>
        </Link>
      </div>

      {loadingOrthos && <div className="loading-state">Загрузка ортофотопланов...</div>}
      
      {errorOrthos && (
        <div className="error-message" style={{ color: 'red', padding: '20px', background: '#ffe6e6', borderRadius: '4px' }}>
          <strong>Ошибка:</strong> {errorOrthos}
          <div style={{ marginTop: '10px' }}>
            <button className="secondary-button" onClick={loadOrthos}>Попробовать снова</button>
          </div>
        </div>
      )}

      {!loadingOrthos && !errorOrthos && orthos.length === 0 && (
        <div className="empty-state">Нет загруженных ортофотопланов</div>
      )}

      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Превью</th>
              <th>Границы (W, S, E, N)</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {orthos.map((ortho) => (
              <tr key={ortho.id}>
                <td>{ortho.filename}</td>
                <td>
                  <div style={{ width: '100px', height: '60px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#eee', borderRadius: '4px' }}>
                    <img 
                      src={ortho.url} 
                      alt="preview" 
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                      onError={(e) => { (e.target as HTMLImageElement).src = 'https://via.placeholder.com/100?text=No+Img'; }}
                    />
                  </div>
                </td>
                <td style={{ fontSize: '0.85em', color: '#555' }}>
                  {ortho.bounds ? (
                    <>
                      <div>W: {ortho.bounds.west.toFixed(6)}</div>
                      <div>S: {ortho.bounds.south.toFixed(6)}</div>
                      <div>E: {ortho.bounds.east.toFixed(6)}</div>
                      <div>N: {ortho.bounds.north.toFixed(6)}</div>
                    </>
                  ) : (
                    <span style={{ fontStyle: 'italic', color: '#999' }}>Нет геоданных</span>
                  )}
                </td>
                <td>
                  <div className="actions-group">
                    <button 
                      className="icon-button" 
                      title="Скачать / Открыть"
                      onClick={() => window.open(ortho.url, '_blank')}
                    >
                      &darr;
                    </button>
                    <button 
                      className="danger-button" 
                      title="Удалить"
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
};

export default ProfileOrthophotos;