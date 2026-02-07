import React, { FC, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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

  const [editId, setEditId] = useState<number | null>(null);
  const [editTags, setEditTags] = useState<string>('');

  useEffect(() => {
    const loadPanoramas = async () => {
      setLoadingPanos(true);
      setErrorPanos('');
      try {
        const data: PanoItem[] = await fetchPanoramas();
        setPanos(data);
      } catch (error) {
        setErrorPanos(error instanceof Error ? error.message : 'Ошибка при загрузке');
      } finally {
        setLoadingPanos(false);
      }
    };
    loadPanoramas();
  }, []);

  const handleEdit = (panoId: number, currentTags: string = '') => {
    setEditId(panoId);
    setEditTags(currentTags);
  };

  const handleSaveTags = async (panoId: number) => {
    try {
      await updatePanoTags(panoId, editTags);
      setPanos((prev) => prev.map((p) => (p.id === panoId ? { ...p, tags: editTags } : p)));
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

  return (
    <div className="table-container" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
      <div className="table-header">
        <h3>Мои панорамы</h3>
        <Link to="/upload">
          <button className="primary-button">+ Загрузить панораму</button>
        </Link>
      </div>

      {loadingPanos && <div>Загрузка панорам...</div>}
      {errorPanos && <div style={{ color: 'red' }}>{errorPanos}</div>}
      {!loadingPanos && !errorPanos && panos.length === 0 && <div className="empty-state">Нет загруженных панорам</div>}

      {!loadingPanos && !errorPanos && panos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th><th>Файл</th><th>Теги</th><th>Координаты</th><th>Дата загрузки</th><th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {panos.map((pano) => (
              <tr key={pano.id}>
                <td>{pano.id}</td>
                <td>{pano.filename}</td>
                <td>
                  {editId === pano.id ? (
                    <input type="text" value={editTags} onChange={(e) => setEditTags(e.target.value)} className="tags-input" />
                  ) : (
                    pano.tags || 'Нет тегов'
                  )}
                </td>
                <td>{pano.latitude && pano.longitude ? `${pano.latitude.toFixed(5)}, ${pano.longitude.toFixed(5)}` : 'N/A'}</td>
                <td>{pano.upload_date ? new Date(pano.upload_date).toLocaleDateString() : '—'}</td>
                <td>
                  <div className="actions-group">
                    {editId === pano.id ? (
                      <button className="success-button" onClick={() => handleSaveTags(pano.id)}>&#10003;</button>
                    ) : (
                      <button className="icon-button" onClick={() => handleEdit(pano.id, pano.tags || '')}>✎</button>
                    )}
                    <button className="danger-button" onClick={() => handleDelete(pano.id)}>&times;</button>
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