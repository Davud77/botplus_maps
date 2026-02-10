// src/components/profile/ProfileOrthophotos.tsx
import React, { FC, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchOrthophotos, deleteOrtho, reprojectOrtho, OrthoItem } from '../../utils/api';

// [FIX] Встроенная SVG заглушка (Data URI). Работает всегда, не вызывает ошибок сети.
const NO_IMAGE_PLACEHOLDER = `data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='60' viewBox='0 0 100 60'%3E%3Crect width='100' height='60' fill='%23eeeeee'/%3E%3Ctext x='50' y='35' font-family='sans-serif' font-size='10' text-anchor='middle' fill='%23999999'%3ENo Preview%3C/text%3E%3C/svg%3E`;

const ProfileOrthophotos: FC = () => {
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState('');
  
  // Состояние для спиннера на конкретной кнопке конвертации
  const [processingId, setProcessingId] = useState<number | null>(null);

  const loadOrthos = async () => {
    setLoadingOrthos(true);
    setErrorOrthos('');
    try {
      const data = await fetchOrthophotos();
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
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка удаления');
    }
  };

  const handleReproject = async (orthoId: number) => {
    if (!window.confirm('Конвертировать в EPSG:3857 (Google Projection)? Это нужно для отображения на карте.')) return;
    
    setProcessingId(orthoId);
    try {
      await reprojectOrtho(orthoId);
      alert('Успешно конвертировано! Список обновляется...');
      await loadOrthos(); 
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ошибка конвертации');
    } finally {
      setProcessingId(null);
    }
  };

  // Хелпер: проверяем, является ли проекция Google/WebMercator
  const isGoogleProjection = (crs?: string) => {
    if (!crs) return false;
    return crs.includes('3857') || crs.includes('Pseudo-Mercator') || crs.includes('Google');
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
              <th>Проекция (CRS)</th>
              <th>Границы (W, S, E, N)</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {orthos.map((ortho) => (
              <tr key={ortho.id}>
                {/* Название */}
                <td style={{maxWidth: '200px', wordBreak: 'break-word'}}>
                  {ortho.filename}
                </td>
                
                {/* Превью */}
                <td>
                  <div style={{ width: '100px', height: '60px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#eee', borderRadius: '4px' }}>
                    <img 
                      src={ortho.url} 
                      alt="preview" 
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                      // [FIX] Используем локальную константу
                      onError={(e) => { (e.target as HTMLImageElement).src = NO_IMAGE_PLACEHOLDER; }}
                    />
                  </div>
                </td>

                {/* Колонка Проекции */}
                <td>
                  <div style={{display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-start'}}>
                    <span style={{
                      display: 'inline-block',
                      background: isGoogleProjection(ortho.crs) ? '#e6fffa' : '#fffbe6',
                      color: isGoogleProjection(ortho.crs) ? '#007a5e' : '#856404',
                      padding: '4px 8px', 
                      borderRadius: '12px', 
                      border: `1px solid ${isGoogleProjection(ortho.crs) ? '#b7eb8f' : '#ffe58f'}`, 
                      fontSize: '0.8em',
                      fontWeight: 500
                    }}>
                      {ortho.crs || 'Не определено'}
                    </span>

                    {!isGoogleProjection(ortho.crs) && (
                      <button 
                        className="secondary-button"
                        style={{
                          fontSize: '0.75em', 
                          padding: '4px 8px', 
                          height: 'auto',
                          lineHeight: 'normal'
                        }}
                        onClick={() => handleReproject(ortho.id)}
                        disabled={processingId === ortho.id}
                      >
                        {processingId === ortho.id ? '⏳ Конвертация...' : 'В Google (3857)'}
                      </button>
                    )}
                  </div>
                </td>

                {/* Границы */}
                <td style={{ fontSize: '0.85em', color: '#555' }}>
                  {ortho.bounds ? (
                    <>
                      <div style={{whiteSpace: 'nowrap'}}>W: {ortho.bounds.west.toFixed(5)}</div>
                      <div style={{whiteSpace: 'nowrap'}}>S: {ortho.bounds.south.toFixed(5)}</div>
                      <div style={{whiteSpace: 'nowrap'}}>E: {ortho.bounds.east.toFixed(5)}</div>
                      <div style={{whiteSpace: 'nowrap'}}>N: {ortho.bounds.north.toFixed(5)}</div>
                    </>
                  ) : (
                    <span style={{ fontStyle: 'italic', color: '#999' }}>Нет геоданных</span>
                  )}
                </td>

                {/* Действия */}
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