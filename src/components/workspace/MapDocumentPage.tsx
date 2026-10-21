import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import MapPage from '../maps/MapPage';
import { useMapStore } from '../maps/hooks/useMapStore';
import { useVectorStore } from '../maps/hooks/useVectorStore';
import { useUIStore } from '../maps/hooks/useUIStore';
import { MapDocument, MapConfig, legacyBasemap, workspaceRequest } from '../../utils/workspaceApi';
import './Workspace.css';
import { useLayerStyleStore } from '../maps/hooks/useLayerStyleStore';
export default function MapDocumentPage() {
  const { mapId } = useParams();
  const [document, setDocument] = useState<MapDocument | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [publication, setPublication] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const view = useRef<MapConfig['view']>({ center: [43,47], zoom: 5 });
  const panoramas = useRef(false);
  const onViewChange = useCallback((next: MapConfig['view']) => { view.current = next; }, []);
  const onPanoramasChange = useCallback((next: boolean) => { panoramas.current = next; }, []);
  useEffect(() => {
    let live = true;
    setReady(false); setError(''); setDocument(null);
    useUIStore.getState().closeAll();
    workspaceRequest<{ map: MapDocument }>(`/maps/${mapId}`).then(async ({ map }) => {
      await useMapStore.getState().fetchOrthos();
      if (!live) return;
      useMapStore.setState({ selectedOrthoIds: map.config.orthophoto_ids, baseLayerUrl: map.config.base_layer_definition?.url ?? legacyBasemap(map.config.base_layer), baseLayerId:map.config.base_layer, baseDefinition:map.config.base_layer_definition||null, coordinateSystem:map.config.coordinate_system||'EPSG:4326' });
      const sources = Object.fromEntries(map.config.vector_layers.map(layer => [`${layer.dbName}-${layer.schema}-${layer.tableName}`, layer]));
      useVectorStore.setState({ activeVectorIds: new Set(Object.keys(sources)), layerSources: sources });
      useLayerStyleStore.setState({layers:(map.config.layer_settings||[]).map(item=>({...item,key:item.key.startsWith('vector:') ? `vector:${Object.keys(sources)[+item.key.slice(7)]}` : item.key}))});
      view.current = map.config.view; panoramas.current = map.config.show_panoramas;
      setDocument(map); setTitle(map.title); setDescription(map.description); setReady(true);
    }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; useUIStore.getState().closeAll(); };
  }, [mapId]);
  async function save() {
    if (!document || pending) return;
    setPending(true); setError(''); setNotice('');
    try {
      const state = useMapStore.getState();
      const vectorState = useVectorStore.getState();
      const vectorIds=[...vectorState.activeVectorIds];
      const config: MapConfig = { view: view.current, base_layer: state.baseLayerId,
        coordinate_system:state.coordinateSystem,
        layer_settings:useLayerStyleStore.getState().layers.map(item=>({...item,key:item.key.startsWith('vector:') ? `vector:${vectorIds.indexOf(item.key.slice(7))}` : item.key})),
        orthophoto_ids: state.selectedOrthoIds, vector_layers: vectorIds.map(id => vectorState.layerSources[id]), show_panoramas: panoramas.current };
      if (config.vector_layers.some(item => !item)) throw new Error('Повторно выберите векторные слои перед сохранением.');
      const result = await workspaceRequest<{ map: MapDocument }>(`/maps/${mapId}`, 'PUT', { title, description, config, revision: document.revision });
      setDocument(result.map); setNotice('Карта сохранена. Публикацию можно обновить отдельно.');
    } catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  async function publish(published: boolean) {
    if (!document || pending) return;
    setPending(true); setError(''); setNotice('');
    try {
      const result = await workspaceRequest<{ map: MapDocument }>(`/maps/${mapId}/publication`, 'POST', { published, revision: document.revision });
      setDocument(result.map); setNotice(published ? 'Сохранённая версия опубликована.' : 'Публикация отключена. Прежняя ссылка больше не работает.');
    } catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  const publicUrl = document?.public_slug ? `${window.location.origin}/p/${document.public_slug}` : '';
  const controls = document && <section className="ws-map-controls" aria-label="Настройки карты">
    <div className="ws-map-control-meta"><Link className="ws-back" to="/">← Все карты</Link><small>{document.can_edit ? 'Редактор карты' : 'Просмотр'} · {document.published ? 'есть публикация' : 'внутренняя карта'}</small></div>
    {document.can_edit ? <input aria-label="Название карты" value={title} maxLength={120} onChange={e => setTitle(e.target.value)} /> : <strong className="ws-map-control-title">{title}</strong>}
    {document.can_edit && <div className="ws-actions"><button className="ws-secondary" aria-expanded={publication} onClick={() => setPublication(!publication)}>Публикация ↗</button><button className="ws-primary" disabled={pending || !title.trim()} onClick={save}>{pending ? 'Сохраняем…' : 'Сохранить карту'}</button></div>}
  </section>;
  return <main className="ws-shell ws-map-editor ws-map-editor-overlay">
    {(error || notice) && <div className={`ws-map-notice ws-notice ${error ? 'ws-error' : ''}`} role={error ? 'alert' : 'status'}>{error || notice}</div>}
    {document?.can_edit && publication && <section className="ws-publication ws-card" aria-label="Настройки публикации"><h2>Поделиться картой</h2><p>Сначала сохраните карту, затем опубликуйте её версию. По ссылке без входа будут доступны выбранные растровые и векторные слои, включая атрибуты объектов. Данные слоёв остаются актуальными.</p>
      <label htmlFor="document-description">Описание карты</label><textarea id="document-description" value={description} maxLength={1000} onChange={e => setDescription(e.target.value)} />
      {publicUrl && <><label htmlFor="public-map-url">Публичная ссылка</label><input id="public-map-url" readOnly value={publicUrl} onFocus={e => e.target.select()} /><div className="ws-actions"><a className="ws-link" href={publicUrl} target="_blank" rel="noreferrer">Открыть публикацию ↗</a><button className="ws-secondary" onClick={async () => { try { await navigator.clipboard.writeText(publicUrl); setNotice('Ссылка скопирована.'); } catch { setNotice('Выделите ссылку и скопируйте её вручную.'); } }}>Копировать</button></div></>}
      <div className="ws-actions"><button className="ws-primary" onClick={() => publish(true)} disabled={pending}>{document.published ? 'Обновить публикацию' : 'Опубликовать сохранённую карту'}</button>{document.published && <button className="ws-secondary" onClick={() => publish(false)} disabled={pending}>Отключить</button>}<button className="ws-secondary" onClick={() => setPublication(false)}>Закрыть</button></div>
      <small>Слой панорам пока доступен только внутри пространства. Для публикации отключите его и сохраните карту.</small>
    </section>}
    <div className="ws-map-stage">{ready && document ? <MapPage key={document.id} initialConfig={document.config} readOnly={!document.can_edit} documentControls={controls} onViewChange={onViewChange} onPanoramasChange={onPanoramasChange} /> : !error && <div className="ws-empty" role="status">Открываем карту…</div>}</div>
  </main>;
}
