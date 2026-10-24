// src/components/profile/ProfileOrthophotos.tsx
import React, { FC, useEffect, useState, useCallback } from 'react';
import {useSettings} from '../../utils/mapSettings';
import {addOperationLog} from '../../utils/operationLogs';
import { Link } from 'react-router-dom';
import {workspaceRequest} from '../../utils/workspaceApi';
import { 
  fetchOrthophotos, 
  deleteOrtho, 
  reprojectOrtho, 
  updateOrtho, 
  OrthoItem
} from '../../utils/api';

const NO_IMAGE_PLACEHOLDER = `data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='60' viewBox='0 0 100 60'%3E%3Crect width='100' height='60' fill='%23eeeeee'/%3E%3Ctext x='50' y='35' font-family='sans-serif' font-size='10' text-anchor='middle' fill='%23999999'%3ENo Preview%3C/text%3E%3C/svg%3E`;

const ProfileOrthophotos: FC = () => {
  const catalog=useSettings(s=>s.data);
  const loadCatalog=useSettings(s=>s.load);
  const [dialog,setDialog]=useState<'rename'|'projection'|null>(null);
  const [name,setName]=useState('');
  const [target,setTarget]=useState('EPSG:3857');
  const [editOpen,setEditOpen]=useState(false);
  const [displayNotice,setDisplayNotice]=useState('');
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState('');
  
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [visibleIds, setVisibleIds] = useState<number[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  const [page,setPage]=useState(0);
  const pageCount=Math.max(1,Math.ceil(orthos.length/50));
  const currentPage=Math.min(page,pageCount-1);
  const pageOrthos=orthos.slice(currentPage*50,(currentPage+1)*50);
  const addLog=useCallback(addOperationLog,[]);

  const loadOrthos = useCallback(async () => {
    setLoadingOrthos(true);
    setErrorOrthos('');
    setSelectedIds([]); 
    addLog('Запрос на получение списка ортофотопланов...', 'info');
    try {
      const data = await fetchOrthophotos();
      if (Array.isArray(data)) {
        
        // ДОБАВЛЕНО: сброс кэша браузера для картинок превью
        const timestamp = Date.now();
        const processedData = data.map(item => ({
            ...item,
            preview_url: item.preview_url ? `${item.preview_url}?t=${timestamp}` : item.preview_url
        }));

        setOrthos(processedData);
        
        const initialVisibleIds = processedData
            .filter(item => item.is_visible === true)
            .map(item => item.id);
        setVisibleIds(initialVisibleIds);
        addLog(`Список успешно обновлен. Загружено файлов: ${processedData.length}`, 'success');
      } else {
        throw new Error('Получены некорректные данные. Ожидался массив JSON.');
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Ошибка при загрузке';
      console.error("Ошибка загрузки ортофотопланов:", error);
      setErrorOrthos(msg);
      addLog(`Ошибка обновления списка: ${msg}`, 'error');
    } finally {
      setLoadingOrthos(false);
    }
  }, [addLog]);

  useEffect(() => {
    loadOrthos();
    loadCatalog().catch(()=>{});
  }, [loadOrthos,loadCatalog]);

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(pageOrthos.map(o => o.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectRow = (id: number) => {
    setSelectedIds(prev => {
      if (prev.includes(id)) return prev.filter(item => item !== id);
      return [...prev, id];
    });
  };

  const handleBulkToggleVisibility = async () => {
    if (selectedIds.length === 0) return;
    
    const allSelectedAreVisible = selectedIds.every(id => visibleIds.includes(id));
    const newVisibilityState = !allSelectedAreVisible;
    
    addLog(`Запуск массового изменения видимости...`, 'info');
    setIsProcessing(true);

    try {
        await Promise.all(selectedIds.map(id => updateOrtho(id, { is_visible: newVisibilityState })));
        if (newVisibilityState) {
            setVisibleIds(Array.from(new Set([...visibleIds, ...selectedIds])));
        } else {
            setVisibleIds(prev => prev.filter(id => !selectedIds.includes(id)));
        }
        setOrthos(prev => prev.map(o => selectedIds.includes(o.id) ? { ...o, is_visible: newVisibilityState } : o));
        addLog(`Видимость успешно обновлена в БД.`, 'success');
    } catch (error) {
        addLog('Ошибка при сохранении видимости в базу данных', 'error');
    } finally {
        setIsProcessing(false);
    }
  };

  async function queueSelected(operation:(id:number)=>Promise<unknown>,items:OrthoItem[]){
    setIsProcessing(true);setDisplayNotice('');
    let added=0;
    try{
      for(const item of items){await operation(item.id);added++;}
      setDisplayNotice(`В очередь добавлено заданий: ${added}. Прогресс — в разделе «Задания».`);
      addLog(`В очередь добавлено заданий: ${added}`);
    }catch(e){const message=(e as Error).message;setDisplayNotice(`Добавлено: ${added}. ${message}`);addLog(message,'error');}
    finally{setIsProcessing(false);}
  }
  const handleBulkReproject=async()=>{
    setDialog(null);
    await queueSelected(id=>reprojectOrtho(id,target),orthos.filter(o=>selectedIds.includes(o.id)&&o.crs!==target));
  };
  const rename=async()=>{
    const id=selectedIds[0];if(!id||!name.trim())return;
    setIsProcessing(true);
    try{
      await updateOrtho(id,{display_name:name.trim()});
      setOrthos(items=>items.map(o=>o.id===id?{...o,display_name:name.trim()}:o));
      setDialog(null);
    }catch(e){setErrorOrthos((e as Error).message);}finally{setIsProcessing(false);}
  };


  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Удалить выбранные объекты (${selectedIds.length} шт.)?`)) return;

    setIsProcessing(true);
    addLog(`Запуск удаления ${selectedIds.length} файлов...`, 'info');
    try {
      await Promise.all(selectedIds.map(async id => {
         await deleteOrtho(id);
         addLog(`Файл ID ${id} удален`, 'success');
      }));
      
      setOrthos(prev => prev.filter(o => !selectedIds.includes(o.id)));
      setSelectedIds([]);
      setVisibleIds(prev => prev.filter(id => !selectedIds.includes(id)));
      addLog('Массовое удаление завершено', 'success');
    } catch (error) {
      addLog(`Ошибка при удалении`, 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkDownload = () => {
    if (selectedIds.length === 0) return;
    if (selectedIds.length > 5 && !window.confirm(`Скачать ${selectedIds.length} файлов сразу?`)) return;

    const items = orthos.filter(o => selectedIds.includes(o.id));
    items.forEach(item => window.open(item.url, '_blank'));
  };

  const prepareForMap=async()=>{
    setIsProcessing(true);setDisplayNotice('');
    try{for(const id of selectedIds)await workspaceRequest(`/raster-display/orthophotos/${id}`,'POST',{});setDisplayNotice('Создание COG для браузера поставлено в очередь. Прогресс и отмена — в разделе «Задания». Оригиналы сохраняются.');}
    catch(e){setDisplayNotice((e as Error).message);}finally{setIsProcessing(false);}
  };

  return (
    <div className="table-container ortho-container">
      <div className="table-header ortho-header-actions">
        <div className="action-buttons-group">
            <button className="secondary-button" onClick={handleBulkToggleVisibility} disabled={!selectedIds.length||isProcessing}>Видимость</button>
            <div className="ortho-edit-menu">
              <button className="secondary-button" aria-label="Редактировать" aria-expanded={editOpen} aria-controls="ortho-edit-actions" onClick={()=>setEditOpen(v=>!v)}>Редактировать ▾</button>
              {editOpen&&<div id="ortho-edit-actions" className="ortho-edit-actions">
                <button className="secondary-button" title="COG для браузера: проекция карты, тайловая структура и пирамиды масштабов. Оригинал сохраняется." onClick={()=>{setEditOpen(false);prepareForMap();}} disabled={!selectedIds.length||isProcessing}>В формат COG</button>
                <button className="secondary-button" onClick={()=>{setEditOpen(false);setDialog('projection');}} disabled={!selectedIds.length||isProcessing}>Сменить проекцию</button>
                <button className="secondary-button" disabled={selectedIds.length!==1||isProcessing} onClick={()=>{setName(orthos.find(o=>o.id===selectedIds[0])?.display_name||orthos.find(o=>o.id===selectedIds[0])?.filename||'');setEditOpen(false);setDialog('rename');}}>Переименовать</button>
              </div>}
            </div>
            <button className="secondary-button" onClick={handleBulkDownload} disabled={selectedIds.length === 0 || isProcessing}>
                Скачать
            </button>
            <button className="secondary-button" onClick={handleBulkDelete} disabled={selectedIds.length === 0 || isProcessing}>
                Удалить
            </button>
        </div>
        <Link className="ws-primary ortho-upload" to="/profile?section=imports&type=raster&mode=upload">Загрузить ортофотопланы</Link>
      </div>
      {dialog&&<section className="ortho-editor ws-card" role="dialog" aria-label={dialog==='rename'?'Переименовать ортофотоплан':'Сменить проекцию'}>
        <h3>{dialog==='rename'?'Переименовать ортофотоплан':'Сменить проекцию'}</h3>
        <form onSubmit={e=>{e.preventDefault();dialog==='rename'?rename():handleBulkReproject();}}>
          {dialog==='rename'?<label>Название ортофотоплана<input autoFocus maxLength={240} required value={name} onChange={e=>setName(e.target.value)}/></label>:<>
            <label>Целевая проекция<select value={target} onChange={e=>setTarget(e.target.value)}>{catalog?.coordinate_systems.filter(c=>c.definition).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <p>В фоне будет создана копия в выбранной проекции. Исходный ортофотоплан сохранится.</p>
          </>}
          <div className="ws-actions"><button className="ws-primary" disabled={isProcessing||(dialog==='rename'?!name.trim():!catalog?.coordinate_systems.some(c=>c.id===target&&c.definition))}>{dialog==='rename'?'Сохранить название':'Создать задание'}</button><button type="button" className="secondary-button" onClick={()=>setDialog(null)}>Отмена</button></div>
        </form>
      </section>}

      {displayNotice&&<p role="status" className="ws-notice">{displayNotice} <Link to="/profile?section=tasks">Открыть задания →</Link></p>}
      {loadingOrthos && <div className="loading-state">Загрузка...</div>}
      {errorOrthos && <div className="error-message ortho-error-message"><strong>Ошибка:</strong> {errorOrthos}</div>}
      {!loadingOrthos && !errorOrthos && orthos.length === 0 && <div className="empty-state">Нет загруженных ортофотопланов</div>}

      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <div className="ortho-table-wrapper">
            <table className="data-table">
            <thead>
                <tr>
                <th className="col-checkbox">
                    <input type="checkbox" checked={pageOrthos.length > 0 && pageOrthos.every(o=>selectedIds.includes(o.id))} onChange={handleSelectAll} />
                </th>
                <th className="ortho-title-column">Ортофотоплан</th>
                <th>Проекция (CRS)</th>
                <th className="col-center">COG</th>
                <th>Статус</th>
                <th>Границы (W, S, E, N)</th>
                <th className="col-center">Видимость</th>
                </tr>
            </thead>
            <tbody>
                {pageOrthos.map((ortho) => {

                    return (
                    <tr key={ortho.id} className={selectedIds.includes(ortho.id) ? 'selected-row' : ''}>
                        <td className="cell-center">
                            <input type="checkbox" checked={selectedIds.includes(ortho.id)} onChange={() => handleSelectRow(ortho.id)} />
                        </td>
                        <td className="ortho-title-cell" data-label="Ортофотоплан">
                          <div className="ortho-identity">
                            <div className="preview-wrapper">
                              <img src={ortho.preview_url || NO_IMAGE_PLACEHOLDER} alt={`Превью: ${ortho.display_name||ortho.filename}`} loading="lazy" decoding="async" className="preview-image" onError={e=>{e.currentTarget.onerror=null;e.currentTarget.src=NO_IMAGE_PLACEHOLDER;}}/>
                            </div>
                            <div className="ortho-title"><strong title={ortho.display_name||ortho.filename}>{ortho.display_name||ortho.filename}</strong><small>{ortho.display_name&&ortho.display_name!==ortho.filename?ortho.filename:'GeoTIFF · Ортофотоплан'}</small></div>
                          </div>
                        </td>
                        <td data-label="Проекция">
                            <span className={`badge-crs ${ortho.crs && (ortho.crs.includes('3857') || ortho.crs.includes('Google')) ? 'badge-crs-google' : 'badge-crs-other'}`}>
                                {catalog?.coordinate_systems.find(c=>c.id===ortho.crs)?.name || ortho.crs_name || ortho.crs || 'Не определено'}
                            </span>
                        </td>
                        <td className="cell-center" data-label="COG">
                            <span className={`badge-cog ${ortho.is_cog||ortho.display_ready ? 'badge-cog-yes' : 'badge-cog-no'}`}>{ortho.is_cog||ortho.display_ready ? 'Да' : 'Нет'}</span>
                        </td>
                        <td className="ortho-status" data-label="Статус">
                            <span className="ortho-status-text">{ortho.display_ready?'Быстрый показ подготовлен':'Для карты не подготовлен'}</span>
                        </td>
                        <td className="cell-bounds" data-label="Границы">
                        {ortho.bounds ? (
                            <>
                            <div className="bounds-line">W: {ortho.bounds.west.toFixed(5)}</div>
                            <div className="bounds-line">S: {ortho.bounds.south.toFixed(5)}</div>
                            <div className="bounds-line">E: {ortho.bounds.east.toFixed(5)}</div>
                            <div className="bounds-line">N: {ortho.bounds.north.toFixed(5)}</div>
                            </>
                        ) : <span className="no-bounds">Нет геоданных</span>}
                        </td>
                        <td className="cell-center" data-label="Видимость">
                            <input type="checkbox" checked={visibleIds.includes(ortho.id)} disabled={true} className="checkbox-disabled" />
                        </td>
                    </tr>
                    );
                })}
            </tbody>
            </table>
        </div>
      )}

      <span className="selected-count">{selectedIds.length > 0 ? `Выбрано: ${selectedIds.length}` : 'Выберите элементы'}</span>

      <div className="ws-pagination">
        <button className="secondary-button" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}>Назад</button>
        <span>{currentPage+1} / {pageCount} · {orthos.length} ортофотопланов · по 50 на странице</span>
        <button className="secondary-button" disabled={currentPage+1>=pageCount} onClick={()=>setPage(currentPage+1)}>Далее</button>
      </div>

    </div>
  );
};

export default ProfileOrthophotos;