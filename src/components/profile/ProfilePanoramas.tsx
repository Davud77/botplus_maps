// src/components/profile/ProfilePanoramas.tsx
import React, { FC, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
// [FIX] Импорт функций API
import { fetchPanoramas, updatePanoTags, deletePano } from '../../utils/api';

interface PanoItem {
  id: number;
  filename: string;
  latitude?: number;
  longitude?: number;
  tags?: string;
  upload_date?: string;
}

const ProfilePanoramas: FC = () => {
  const [panos, setPanos] = useState<PanoItem[]>([]);
  const [loadingPanos, setLoadingPanos] = useState(false);
  const [errorPanos, setErrorPanos] = useState('');

  // Состояния для редактирования строки
  const [editId, setEditId] = useState<number | null>(null);
  const [editTags, setEditTags] = useState<string>('');

  // Загрузка данных при монтировании компонента
  useEffect(() => {
    const loadPanoramas = async () => {
      setLoadingPanos(true);
      setErrorPanos('');
      try {
        const data = await fetchPanoramas();
        // Проверка, что пришел массив
        if (Array.isArray(data)) {
            setPanos(data);
        } else {
            throw new Error("Неверный формат данных от сервера");
        }
      } catch (error: any) {
        console.error("Ошибка загрузки панорам:", error);
        setErrorPanos(error.message || 'Ошибка при загрузке');
      } finally {
        setLoadingPanos(false);
      }
    };
    loadPanoramas();
  }, []);

  // Вход в режим редактирования
  const handleEdit = (panoId: number, currentTags: string = '') => {
    setEditId(panoId);
    setEditTags(currentTags || '');
  };

  // Сохранение изменений
  const handleSaveTags = async (panoId: number) => {
    try {
      await updatePanoTags(panoId, editTags);
      
      // Обновляем локальный стейт
      setPanos((prev) => prev.map((p) => (p.id === panoId ? { ...p, tags: editTags } : p)));
      
      setEditId(null);
      setEditTags('');
    } catch (error: any) {
      alert(error.message || 'Ошибка сохранения тегов');
    }
  };

  // Отмена редактирования
  const handleCancelEdit = () => {
    setEditId(null);
    setEditTags('');
  };

  // Удаление панорамы
  const handleDelete = async (panoId: number) => {
    if (!window.confirm('Уверены, что хотите удалить панораму? Это действие необратимо.')) return;
    try {
      await deletePano(panoId);
      setPanos((prev) => prev.filter((p) => p.id !== panoId));
    } catch (error: any) {
      alert(error.message || 'Ошибка удаления');
    }
  };

  return (
    <div className="table-container" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
      <div className="table-header">
        <h3>Мои панорамы (360°)</h3>
        <Link to="/upload">
          <button className="primary-button">+ Загрузить панораму</button>
        </Link>
      </div>

      {loadingPanos && <div className="loading-state">Загрузка списка панорам...</div>}
      
      {errorPanos && <div className="error-message" style={{ color: 'red', padding: '10px' }}>{errorPanos}</div>}
      
      {!loadingPanos && !errorPanos && panos.length === 0 && (
        <div className="empty-state">Нет загруженных панорам</div>
      )}

      {!loadingPanos && !errorPanos && panos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>ID</th>
              <th>Файл</th>
              <th>Теги</th>
              <th>Координаты</th>
              <th>Дата загрузки</th>
              <th style={{ width: '120px' }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {panos.map((pano) => (
              <tr key={pano.id}>
                <td>{pano.id}</td>
                <td title={pano.filename} style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {pano.filename}
                </td>
                <td>
                  {editId === pano.id ? (
                    <input 
                        type="text" 
                        value={editTags} 
                        onChange={(e) => setEditTags(e.target.value)} 
                        className="tags-input" 
                        autoFocus
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveTags(pano.id);
                            if (e.key === 'Escape') handleCancelEdit();
                        }}
                    />
                  ) : (
                    pano.tags ? <span className="tag-badge">{pano.tags}</span> : <span style={{color: '#ccc', fontStyle: 'italic'}}>Нет тегов</span>
                  )}
                </td>
                <td>
                    {pano.latitude && pano.longitude ? (
                        <a 
                           href={`https://www.google.com/maps?q=${pano.latitude},${pano.longitude}`} 
                           target="_blank" 
                           rel="noreferrer"
                           className="coord-link"
                           style={{ color: '#2196f3', textDecoration: 'none' }}
                        >
                            {pano.latitude.toFixed(5)}, {pano.longitude.toFixed(5)}
                        </a>
                    ) : 'N/A'}
                </td>
                <td>
                    {pano.upload_date ? new Date(pano.upload_date).toLocaleDateString('ru-RU') : '—'}
                </td>
                <td>
                  <div className="actions-group">
                    {editId === pano.id ? (
                      <>
                        <button className="success-button small" onClick={() => handleSaveTags(pano.id)} title="Сохранить">✓</button>
                        <button className="secondary-button small" onClick={handleCancelEdit} title="Отмена">✕</button>
                      </>
                    ) : (
                      <button className="icon-button" onClick={() => handleEdit(pano.id, pano.tags)} title="Редактировать">✎</button>
                    )}
                    <button className="danger-button" onClick={() => handleDelete(pano.id)} title="Удалить">🗑</button>
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

export default ProfilePanoramas;