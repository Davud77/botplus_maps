import React, { FC, useCallback, useEffect, useState } from 'react';
import { fetchVectorDbs, fetchVectorLayers, createVectorDb, createVectorLayer, VectorDbItem } from '../../utils/api';
import { useAuth } from '../../hooks/useAuth';

const ProfileVector: FC = () => {
  const { user } = useAuth();
  const editable = user?.role !== 'viewer';
  const [databases, setDatabases] = useState<VectorDbItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showDatabaseForm, setShowDatabaseForm] = useState(false);
  const [databaseName, setDatabaseName] = useState('');
  const [layerDatabase, setLayerDatabase] = useState<string | null>(null);
  const [layerName, setLayerName] = useState('');
  const [geometry, setGeometry] = useState('POINT');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const dbs = await fetchVectorDbs();
      const rows = await Promise.all(dbs.map(async db => {
        try { return { ...db, layers: await fetchVectorLayers(db.name) }; }
        catch { return { ...db, layers: [], status: 'error' as const }; }
      }));
      setDatabases(rows.sort((a,b) => a.name.localeCompare(b.name)));
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function createDatabase(event: React.FormEvent) {
    event.preventDefault(); setPending(true); setError(''); setNotice('');
    try { await createVectorDb(databaseName); setShowDatabaseForm(false); setDatabaseName(''); setNotice('База данных создана.'); await load(); }
    catch (e) { setError((e as Error).message); }
    finally { setPending(false); }
  }
  async function createLayer(event: React.FormEvent) {
    event.preventDefault(); if (!layerDatabase) return;
    setPending(true); setError(''); setNotice('');
    try { await createVectorLayer(layerDatabase, layerName, geometry); setLayerDatabase(null); setLayerName(''); setNotice('Слой создан.'); await load(); }
    catch (e) { setError((e as Error).message); }
    finally { setPending(false); }
  }
  return <div className="ws-postgis">
    <div className="ws-page-heading"><div><div className="ws-section-kicker">ВЕКТОРНЫЕ ДАННЫЕ</div><h2>PostGIS</h2><p>Базы данных, схемы и пространственные слои.</p></div>
      <div className="ws-postgis-actions"><button className="ws-secondary" disabled={loading || pending} onClick={() => { setError(''); load(); }}>Обновить</button>{user?.role === 'admin' && <button className="ws-primary" disabled={pending} onClick={() => setShowDatabaseForm(value => !value)}>Создать базу</button>}</div></div>
    {error && <p role="alert" className="ws-notice ws-error">{error}</p>}{notice && <p role="status" className="ws-notice">{notice}</p>}
    {showDatabaseForm && user?.role === 'admin' && <form className="ws-postgis-form" onSubmit={createDatabase}><div><label htmlFor="postgis-db-name">Название базы</label><input id="postgis-db-name" value={databaseName} maxLength={63} required pattern="[a-zA-Z][a-zA-Z0-9]*" placeholder="Например, survey2026" disabled={pending} onChange={e => setDatabaseName(e.target.value)} /><small>Латинские буквы и цифры, первая — буква.</small></div><button className="ws-primary" disabled={pending}>Создать</button><button type="button" className="ws-secondary" disabled={pending} onClick={() => setShowDatabaseForm(false)}>Отмена</button></form>}
    {loading ? <p role="status">Загрузка PostGIS…</p> : !databases.length ? <div className="ws-postgis-empty">Доступных баз данных пока нет.</div> : databases.map(db => {
      const schemas = Array.from(new Set((db.layers || []).map(layer => layer.schema || 'public'))).sort();
      return <article className="ws-postgis-database" key={db.id}><div className="ws-postgis-heading"><div><h3>{db.name}</h3><p>{db.type === 'internal' ? 'Локальная база' : 'Внешняя база'} · {(db.layers || []).length} слоёв</p></div><span className={`ws-badge ${db.status === 'connected' ? 'green' : ''}`}>{db.status === 'connected' ? 'Подключена' : 'Недоступна'}</span>{editable && db.status === 'connected' && <button className="ws-secondary" disabled={pending} onClick={() => { setLayerDatabase(db.name); setLayerName(''); setGeometry('POINT'); }}>Создать слой</button>}</div>
        {layerDatabase === db.name && <form className="ws-postgis-form" onSubmit={createLayer}><div><label htmlFor="postgis-layer-name">Название таблицы</label><input id="postgis-layer-name" required maxLength={63} pattern="[a-zA-Z_][a-zA-Z0-9_]*" value={layerName} placeholder="Например, survey_points" disabled={pending} onChange={e => setLayerName(e.target.value)} /><small>Схема public · проекция EPSG:4326</small></div><div><label htmlFor="postgis-geometry">Геометрия</label><select id="postgis-geometry" value={geometry} disabled={pending} onChange={e => setGeometry(e.target.value)}><option value="POINT">Точки</option><option value="LINESTRING">Линии</option><option value="POLYGON">Полигоны</option></select></div><button className="ws-primary" disabled={pending}>Создать</button><button type="button" className="ws-secondary" disabled={pending} onClick={() => setLayerDatabase(null)}>Отмена</button></form>}
        {db.status === 'error' ? <p role="status">Не удалось прочитать слои. Проверьте подключение и обновите список.</p> : !schemas.length ? <p className="ws-postgis-empty">Пространственных слоёв пока нет.</p> : schemas.map(schema => <section className="ws-postgis-schema" key={schema}><div className="ws-postgis-schema-title"><span>Схема</span><strong>{schema}</strong></div><div className="ws-postgis-table"><table><thead><tr><th>Таблица</th><th>Геометрия</th><th>Проекция</th><th>Объектов</th></tr></thead><tbody>{(db.layers || []).filter(layer => (layer.schema || 'public') === schema).sort((a,b) => a.tableName.localeCompare(b.tableName)).map(layer => <tr key={layer.id}><td><strong>{layer.tableName}</strong></td><td><span className="ws-badge">{layer.geometryType}</span></td><td>{layer.srid ? `EPSG:${layer.srid}` : 'Не задана'}</td><td>{layer.featureCount == null ? '—' : layer.featureCount.toLocaleString('ru-RU')}</td></tr>)}</tbody></table></div></section>)}
      </article>;
    })}
  </div>;
};
export default ProfileVector;
