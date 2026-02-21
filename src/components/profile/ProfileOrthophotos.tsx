// src/components/profile/ProfileOrthophotos.tsx
import React, { FC, useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  fetchOrthophotos, 
  deleteOrtho, 
  reprojectOrtho, 
  processOrthoCog, 
  updateOrtho, 
  getTaskStatus,
  generateOrthoPreview,
  OrthoItem,
  TaskStartResponse
} from '../../utils/api';

const NO_IMAGE_PLACEHOLDER = `data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='60' viewBox='0 0 100 60'%3E%3Crect width='100' height='60' fill='%23eeeeee'/%3E%3Ctext x='50' y='35' font-family='sans-serif' font-size='10' text-anchor='middle' fill='%23999999'%3ENo Preview%3C/text%3E%3C/svg%3E`;

interface LogEntry {
  id: number;
  time: string;
  message: string;
  type: 'info' | 'success' | 'error';
}

const ProfileOrthophotos: FC = () => {
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState('');
  
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [visibleIds, setVisibleIds] = useState<number[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Состояние для хранения прогресса отдельных файлов
  const [rowProgress, setRowProgress] = useState<Record<number, number>>({});

  // Состояние активных задач с инициализацией из LocalStorage
  const [activeTasks, setActiveTasks] = useState<Record<number, string>>(() => {
    const saved = localStorage.getItem('active_ortho_tasks');
    return saved ? JSON.parse(saved) : {};
  });

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const addLog = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
    setLogs(prev => [...prev, {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString('ru-RU'),
      message,
      type
    }]);
  };

  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, showLogs]);

  // Сохраняем активные задачи в LocalStorage при любом изменении
  useEffect(() => {
    localStorage.setItem('active_ortho_tasks', JSON.stringify(activeTasks));
  }, [activeTasks]);

  // Возобновление поллинга при загрузке (если были незаконченные задачи)
  useEffect(() => {
    Object.entries(activeTasks).forEach(([orthoIdStr, taskId]) => {
      const orthoId = Number(orthoIdStr);
      setRowProgress(prev => ({ ...prev, [orthoId]: 0 })); // Показываем полоску
      pollTask(taskId, orthoId).then(() => {
          loadOrthos(); // Обновляем список, когда задача доделается
      }).catch((e) => {
          addLog(`Ошибка в фоновой задаче ${orthoId}: ${e.message}`, 'error');
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadOrthos = async () => {
    setLoadingOrthos(true);
    setErrorOrthos('');
    setSelectedIds([]); 
    addLog('Запрос на получение списка ортофотопланов...', 'info');
    try {
      const data = await fetchOrthophotos();
      if (Array.isArray(data)) {
        setOrthos(data);
        const initialVisibleIds = data
            .filter(item => item.is_visible === true)
            .map(item => item.id);
        setVisibleIds(initialVisibleIds);
        addLog(`Список успешно обновлен. Загружено файлов: ${data.length}`, 'success');
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
  };

  useEffect(() => {
    loadOrthos();
  }, []);

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(orthos.map(o => o.id));
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

  // [UPDATED] Улучшенная функция поллинга с защитой от бесконечного цикла (отлов 404)
  const pollTask = async (taskId: string, orthoId: number) => {
    return new Promise<void>((resolve, reject) => {
      let errorCount = 0; // Счетчик ошибок подряд
      
      const interval = setInterval(async () => {
        try {
          const statusData = await getTaskStatus(taskId);
          errorCount = 0; // Если запрос успешен, сбрасываем счетчик
          
          if (statusData.status === 'processing' || statusData.status === 'pending') {
            setRowProgress(prev => ({ ...prev, [orthoId]: statusData.progress }));
          } else if (statusData.status === 'success') {
            clearInterval(interval);
            setRowProgress(prev => ({ ...prev, [orthoId]: 100 }));
            
            // Удаляем задачу из памяти
            setActiveTasks(prev => {
                const next = { ...prev };
                delete next[orthoId];
                return next;
            });
            resolve();
          } else if (statusData.status === 'error') {
            clearInterval(interval);
            setRowProgress(prev => {
                const newState = { ...prev };
                delete newState[orthoId];
                return newState;
            });
            
            // Удаляем задачу из памяти при ошибке
            setActiveTasks(prev => {
                const next = { ...prev };
                delete next[orthoId];
                return next;
            });
            reject(new Error(statusData.error || 'Unknown error'));
          }
        } catch (e: any) {
          console.error("Polling error", e);
          errorCount++;
          
          // Если сервер вернул 404 (задачи больше нет) или слишком много ошибок
          if ((e.message && e.message.includes('404')) || errorCount > 10) {
              clearInterval(interval);
              
              setRowProgress(prev => {
                  const newState = { ...prev };
                  delete newState[orthoId];
                  return newState;
              });
              
              setActiveTasks(prev => {
                  const next = { ...prev };
                  delete next[orthoId];
                  return next;
              });
              
              reject(new Error("Задача потеряна сервером (возможно, был перезапуск)"));
          }
        }
      }, 1000); 
    });
  };

  const handleBulkCreatePreview = async () => {
    if (selectedIds.length === 0) return;
    const itemsToProcess = orthos.filter(o => selectedIds.includes(o.id) && !o.preview_url);
    if (itemsToProcess.length === 0) {
        alert('Для всех выбранных файлов уже сгенерированы превью.'); return;
    }
    if (!window.confirm(`Сгенерировать превью для (${itemsToProcess.length} шт.)?`)) return;

    setIsProcessing(true);
    addLog(`Запуск генерации превью для ${itemsToProcess.length} файлов...`, 'info');
    
    const initialProgress = { ...rowProgress };
    itemsToProcess.forEach(i => initialProgress[i.id] = 0);
    setRowProgress(initialProgress);

    try {
      const tasks = await Promise.all(itemsToProcess.map(async (item) => {
        try {
            const response = await generateOrthoPreview(item.id);
            return { orthoId: item.id, taskId: response.task_id, filename: item.filename };
        } catch (e) {
            return null;
        }
      }));

      const validTasks = tasks.filter(t => t !== null) as { orthoId: number, taskId: string, filename: string }[];
      
      // Регистрируем в LocalStorage перед поллингом
      setActiveTasks(prev => {
          const next = { ...prev };
          validTasks.forEach(t => next[t.orthoId] = t.taskId);
          return next;
      });

      await Promise.all(validTasks.map(async (task) => {
          try {
              await pollTask(task.taskId, task.orthoId);
              addLog(`Превью готово: ${task.filename}`, 'success');
          } catch (e: any) {
              addLog(`Ошибка генерации ${task.filename}: ${e.message}`, 'error');
          }
      }));

      setRowProgress({});
      await loadOrthos();
    } catch (error) {
      addLog('Ошибка при массовой генерации превью', 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkReproject = async () => {
    if (selectedIds.length === 0) return;
    const isGoogleProjection = (crs?: string) => crs ? (crs.includes('3857') || crs.includes('Pseudo-Mercator') || crs.includes('Google')) : false;
    const itemsToProcess = orthos.filter(o => selectedIds.includes(o.id) && !isGoogleProjection(o.crs));
    
    if (itemsToProcess.length === 0) {
        alert('Все выбранные файлы уже находятся в проекции EPSG:3857.'); return;
    }
    if (!window.confirm(`Конвертировать (${itemsToProcess.length} шт.) в EPSG:3857?`)) return;

    setIsProcessing(true);
    addLog(`Запуск перепроецирования в EPSG:3857...`, 'info');
    
    const initialProgress = { ...rowProgress };
    itemsToProcess.forEach(i => initialProgress[i.id] = 0);
    setRowProgress(initialProgress);

    try {
      const tasks = await Promise.all(itemsToProcess.map(async (item) => {
        try {
            const response = await reprojectOrtho(item.id);
            return { orthoId: item.id, taskId: response.task_id, filename: item.filename };
        } catch (e) {
            return null;
        }
      }));

      const validTasks = tasks.filter(t => t !== null) as { orthoId: number, taskId: string, filename: string }[];

      // Сохраняем активные таски в память
      setActiveTasks(prev => {
          const next = { ...prev };
          validTasks.forEach(t => next[t.orthoId] = t.taskId);
          return next;
      });

      await Promise.all(validTasks.map(async (task) => {
          try {
              await pollTask(task.taskId, task.orthoId);
              addLog(`Завершено: ${task.filename}`, 'success');
          } catch (e: any) {
              addLog(`Сбой обработки ${task.filename}: ${e.message}`, 'error');
          }
      }));

      setRowProgress({}); 
      await loadOrthos();
    } catch (error) {
      addLog('Произошла ошибка при массовой обработке 3857', 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkProcessCOG = async () => {
    if (selectedIds.length === 0) return;
    const itemsToProcess = orthos.filter(o => selectedIds.includes(o.id) && !o.is_cog);
    
    if (itemsToProcess.length === 0) {
        alert('Все выбранные файлы уже оптимизированы (COG).'); return;
    }
    if (!window.confirm(`Оптимизировать (${itemsToProcess.length} шт.) в формат COG?`)) return;

    setIsProcessing(true);
    addLog(`Запуск оптимизации в COG...`, 'info');

    const initialProgress = { ...rowProgress };
    itemsToProcess.forEach(i => initialProgress[i.id] = 0);
    setRowProgress(initialProgress);

    try {
      const tasks = await Promise.all(itemsToProcess.map(async (item) => {
        try {
            const response = await processOrthoCog(item.id);
            return { orthoId: item.id, taskId: response.task_id, filename: item.filename };
        } catch (e) {
            return null;
        }
      }));

      const validTasks = tasks.filter(t => t !== null) as { orthoId: number, taskId: string, filename: string }[];

      // Запоминаем задачи в LocalStorage
      setActiveTasks(prev => {
          const next = { ...prev };
          validTasks.forEach(t => next[t.orthoId] = t.taskId);
          return next;
      });

      await Promise.all(validTasks.map(async (task) => {
          try {
              await pollTask(task.taskId, task.orthoId);
              addLog(`Оптимизирован: ${task.filename}`, 'success');
          } catch (e: any) {
              addLog(`Ошибка COG ${task.filename}: ${e.message}`, 'error');
          }
      }));
      
      setRowProgress({});
      await loadOrthos();
    } catch (error) {
      addLog('Произошла ошибка при массовой оптимизации COG', 'error');
    } finally {
      setIsProcessing(false);
    }
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
      setRowProgress(prev => {
         const next = { ...prev };
         selectedIds.forEach(id => delete next[id]);
         return next;
      });
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

  return (
    <div className="table-container ortho-container">
      <div className="table-header ortho-header-actions">
        <div className="action-buttons-group">
            <button className="secondary-button" onClick={handleBulkToggleVisibility} disabled={selectedIds.length === 0 || isProcessing}>
                Видимость
            </button>
            <button className="secondary-button" onClick={handleBulkCreatePreview} disabled={selectedIds.length === 0 || isProcessing}>
                Создать превью
            </button>
            <button className="secondary-button" onClick={handleBulkProcessCOG} disabled={selectedIds.length === 0 || isProcessing}>
                {isProcessing ? 'Wait...' : 'В формат COG'}
            </button>
            <button className="secondary-button" onClick={handleBulkReproject} disabled={selectedIds.length === 0 || isProcessing}>
                {isProcessing ? 'Wait...' : 'В EPSG:3857'}
            </button>
            <button className="secondary-button" onClick={handleBulkDownload} disabled={selectedIds.length === 0 || isProcessing}>
                Скачать
            </button>
            <button className="secondary-button" onClick={handleBulkDelete} disabled={selectedIds.length === 0 || isProcessing}>
                Удалить
            </button>
        </div>

        <div className="right-buttons-group">
            <button className="secondary-button" onClick={loadOrthos} disabled={loadingOrthos || isProcessing}>
                {loadingOrthos ? '⏳' : 'Обновить'}
            </button>
            <Link to="/uploadortho">
                <button className="primary-button">+ Загрузить</button>
            </Link>
        </div>
      </div>

      {loadingOrthos && <div className="loading-state">Загрузка...</div>}
      {errorOrthos && <div className="error-message ortho-error-message"><strong>Ошибка:</strong> {errorOrthos}</div>}
      {!loadingOrthos && !errorOrthos && orthos.length === 0 && <div className="empty-state">Нет загруженных ортофотопланов</div>}

      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <div className="ortho-table-wrapper">
            <table className="data-table">
            <thead>
                <tr>
                <th className="col-checkbox">
                    <input type="checkbox" checked={selectedIds.length === orthos.length && orthos.length > 0} onChange={handleSelectAll} />
                </th>
                <th>Название</th>
                <th>Превью</th>
                <th>Проекция (CRS)</th>
                <th className="col-center">COG</th>
                <th>Статус / Прогресс</th>
                <th>Границы (W, S, E, N)</th>
                <th className="col-center">Видимость</th>
                </tr>
            </thead>
            <tbody>
                {orthos.map((ortho) => {
                    const progress = rowProgress[ortho.id];
                    const hasProgress = progress !== undefined;

                    return (
                    <tr key={ortho.id} className={selectedIds.includes(ortho.id) ? 'selected-row' : ''}>
                        <td className="cell-center">
                            <input type="checkbox" checked={selectedIds.includes(ortho.id)} onChange={() => handleSelectRow(ortho.id)} />
                        </td>
                        <td className="cell-filename">{ortho.filename}</td>
                        <td>
                        <div className="preview-wrapper">
                            <img src={ortho.preview_url || NO_IMAGE_PLACEHOLDER} alt="preview" className="preview-image" onError={(e) => { (e.target as HTMLImageElement).src = NO_IMAGE_PLACEHOLDER; }} />
                        </div>
                        </td>
                        <td>
                            <span className={`badge-crs ${ortho.crs && (ortho.crs.includes('3857') || ortho.crs.includes('Google')) ? 'badge-crs-google' : 'badge-crs-other'}`}>
                                {ortho.crs || 'Не определено'}
                            </span>
                        </td>
                        <td className="cell-center">
                            <span className={`badge-cog ${ortho.is_cog ? 'badge-cog-yes' : 'badge-cog-no'}`}>{ortho.is_cog ? 'Да' : 'Нет'}</span>
                        </td>
                        <td style={{ width: '200px' }}>
                            {hasProgress ? (
                                <div className="progress-wrapper">
                                    <div className="progress-text">
                                        <span>Обработка...</span>
                                        <span>{progress}%</span>
                                    </div>
                                    <div className="progress-track">
                                        <div className="progress-fill" style={{ width: `${progress}%` }} />
                                    </div>
                                </div>
                            ) : (
                                <span className="status-ready">Готов к работе</span>
                            )}
                        </td>
                        <td className="cell-bounds">
                        {ortho.bounds ? (
                            <>
                            <div className="bounds-line">W: {ortho.bounds.west.toFixed(5)}</div>
                            <div className="bounds-line">S: {ortho.bounds.south.toFixed(5)}</div>
                            <div className="bounds-line">E: {ortho.bounds.east.toFixed(5)}</div>
                            <div className="bounds-line">N: {ortho.bounds.north.toFixed(5)}</div>
                            </>
                        ) : <span className="no-bounds">Нет геоданных</span>}
                        </td>
                        <td className="cell-center">
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

      <div className="log-container">
        <div className="log-header" onClick={() => setShowLogs(!showLogs)}>
            <span>Системные логи ({logs.length})</span>
            <span>{showLogs ? '▼' : '▲'}</span>
        </div>
        {showLogs && (
            <div className="log-body">
                {logs.length === 0 ? <div className="log-empty">Логи пусты. Начните работу с файлами.</div> : 
                    logs.map(log => (
                        <div key={log.id} className="log-entry">
                            <span className="log-time">[{log.time}]</span>
                            <span className={`log-msg log-${log.type}`}>{log.message}</span>
                        </div>
                    ))
                }
                <div ref={logsEndRef} />
            </div>
        )}
      </div>
    </div>
  );
};

export default ProfileOrthophotos;