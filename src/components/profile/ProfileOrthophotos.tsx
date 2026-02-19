// src/components/profile/ProfileOrthophotos.tsx
import React, { FC, useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  fetchOrthophotos, 
  deleteOrtho, 
  reprojectOrtho, 
  processOrthoCog, 
  updateOrtho, 
  getTaskStatus, // [NEW]
  OrthoItem,
  TaskStartResponse // [NEW]
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

  // [NEW] Состояние для хранения прогресса отдельных файлов по их ID
  // key: ortho_id, value: percentage (0-100)
  const [rowProgress, setRowProgress] = useState<Record<number, number>>({});

  // [NEW] Состояние для логов и UI логов
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Функция добавления лога
  const addLog = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
    setLogs(prev => [...prev, {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString('ru-RU'),
      message,
      type
    }]);
  };

  // Автоскролл логов
  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, showLogs]);

  const loadOrthos = async () => {
    setLoadingOrthos(true);
    setErrorOrthos('');
    setSelectedIds([]); 
    addLog('Запрос на получение списка ортофотопланов...', 'info');
    try {
      const data = await fetchOrthophotos();
      if (Array.isArray(data)) {
        setOrthos(data);
        
        // [UPDATED] Инициализируем visibleIds на основе данных из БД
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

  // [UPDATED] Логика кнопки "Видимость" с сохранением в БД
  const handleBulkToggleVisibility = async () => {
    if (selectedIds.length === 0) return;
    
    const allSelectedAreVisible = selectedIds.every(id => visibleIds.includes(id));
    const newVisibilityState = !allSelectedAreVisible; // true = показать, false = скрыть
    
    const actionText = newVisibilityState ? 'ВКЛЮЧЕНИЕ' : 'ВЫКЛЮЧЕНИЕ';
    addLog(`Запуск массового изменения видимости (${actionText}) для ${selectedIds.length} файлов...`, 'info');
    setIsProcessing(true);

    try {
        await Promise.all(selectedIds.map(id => 
            updateOrtho(id, { is_visible: newVisibilityState })
        ));

        if (newVisibilityState) {
            const newSet = new Set([...visibleIds, ...selectedIds]);
            setVisibleIds(Array.from(newSet));
        } else {
            setVisibleIds(prev => prev.filter(id => !selectedIds.includes(id)));
        }

        setOrthos(prev => prev.map(o => 
            selectedIds.includes(o.id) ? { ...o, is_visible: newVisibilityState } : o
        ));

        addLog(`Видимость успешно обновлена в БД. Новое состояние: ${newVisibilityState ? 'Видимы' : 'Скрыты'}`, 'success');

    } catch (error) {
        console.error("Ошибка при обновлении видимости:", error);
        addLog('Ошибка при сохранении видимости в базу данных', 'error');
        alert('Не удалось сохранить состояние видимости. Проверьте консоль.');
    } finally {
        setIsProcessing(false);
    }
  };

  const handleBulkCreatePreview = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Сгенерировать превью для выбранных файлов (${selectedIds.length} шт.)?`)) return;

    setIsProcessing(true);
    addLog(`Запуск генерации превью для ${selectedIds.length} файлов...`, 'info');
    try {
      await new Promise(resolve => setTimeout(resolve, 1000));
      addLog('Запрос на генерацию превью успешно отправлен (функция в разработке)', 'success');
      alert('Запрос на генерацию превью отправлен (функция в разработке)');
    } catch (error) {
      addLog('Ошибка при создании превью', 'error');
      alert('Ошибка при создании превью');
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
      // Очищаем прогресс бары удаленных файлов, если были
      setRowProgress(prev => {
         const next = { ...prev };
         selectedIds.forEach(id => delete next[id]);
         return next;
      });
      addLog('Массовое удаление завершено', 'success');
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Ошибка при удалении';
      addLog(`Ошибка при удалении: ${msg}`, 'error');
      alert(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  // [NEW] Вспомогательная функция для поллинга задачи
  const pollTask = async (taskId: string, orthoId: number) => {
    return new Promise<void>((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const statusData = await getTaskStatus(taskId);
          
          if (statusData.status === 'processing' || statusData.status === 'pending') {
            // Обновляем прогресс в стейте
            setRowProgress(prev => ({ ...prev, [orthoId]: statusData.progress }));
          } else if (statusData.status === 'success') {
            clearInterval(interval);
            setRowProgress(prev => ({ ...prev, [orthoId]: 100 }));
            resolve();
          } else if (statusData.status === 'error') {
            clearInterval(interval);
            setRowProgress(prev => {
                const newState = { ...prev };
                delete newState[orthoId]; // Удаляем прогресс бар при ошибке
                return newState;
            });
            reject(new Error(statusData.error || 'Unknown error'));
          }
        } catch (e) {
          console.error("Polling error", e);
          // Не прерываем сразу, вдруг сеть моргнула.
        }
      }, 1000); // Опрос раз в секунду
    });
  };

  // [MODIFIED] Массовое перепроецирование с прогрессом
  const handleBulkReproject = async () => {
    if (selectedIds.length === 0) return;
    const itemsToProcess = orthos.filter(o => selectedIds.includes(o.id));
    
    if (!window.confirm(`Конвертировать выбранные (${itemsToProcess.length} шт.) в EPSG:3857?`)) return;

    setIsProcessing(true);
    addLog(`Запуск перепроецирования в EPSG:3857 для ${itemsToProcess.length} файлов...`, 'info');
    
    // Сбрасываем прогресс для выбранных
    const initialProgress = { ...rowProgress };
    itemsToProcess.forEach(i => initialProgress[i.id] = 0);
    setRowProgress(initialProgress);

    try {
      // 1. Запускаем все задачи
      const tasks = await Promise.all(itemsToProcess.map(async (item) => {
        try {
            addLog(`Инициализация задачи для: ${item.filename}`, 'info');
            const response = await reprojectOrtho(item.id);
            return { orthoId: item.id, taskId: response.task_id, filename: item.filename };
        } catch (e) {
            addLog(`Ошибка запуска задачи для ${item.filename}: ${e}`, 'error');
            console.error(`Ошибка конвертации ID ${item.id}`, e);
            return null;
        }
      }));

      const validTasks = tasks.filter(t => t !== null) as { orthoId: number, taskId: string, filename: string }[];

      // 2. Ожидаем завершения всех задач через поллинг
      await Promise.all(validTasks.map(async (task) => {
          try {
              await pollTask(task.taskId, task.orthoId);
              addLog(`Завершено: ${task.filename}`, 'success');
          } catch (e: any) {
              addLog(`Сбой обработки ${task.filename}: ${e.message}`, 'error');
          }
      }));

      addLog('Процесс перепроецирования завершен. Обновление списка...', 'success');
      alert('Обработка завершена. Список обновляется...');
      
      // Очищаем прогресс бары
      setRowProgress({}); 
      await loadOrthos();

    } catch (error) {
      addLog('Произошла критическая ошибка при массовой обработке 3857', 'error');
      alert('Произошла ошибка при массовой обработке');
    } finally {
      setIsProcessing(false);
    }
  };

  // [MODIFIED] Функция конвертации в COG с прогрессом
  const handleBulkProcessCOG = async () => {
    if (selectedIds.length === 0) return;
    const itemsToProcess = orthos.filter(o => selectedIds.includes(o.id));
    
    if (!window.confirm(`Оптимизировать выбранные (${itemsToProcess.length} шт.) в формат COG?`)) return;

    setIsProcessing(true);
    addLog(`Запуск оптимизации в COG для ${itemsToProcess.length} файлов...`, 'info');

    // Инициализация прогресс-баров
    const initialProgress = { ...rowProgress };
    itemsToProcess.forEach(i => initialProgress[i.id] = 0);
    setRowProgress(initialProgress);

    try {
      // 1. Запуск задач на сервере
      const tasks = await Promise.all(itemsToProcess.map(async (item) => {
        try {
            addLog(`Старт оптимизации: ${item.filename}`, 'info');
            const response = await processOrthoCog(item.id);
            return { orthoId: item.id, taskId: response.task_id, filename: item.filename };
        } catch (e) {
            addLog(`Ошибка запуска для ${item.filename}: ${e}`, 'error');
            console.error(`Ошибка COG ID ${item.id}`, e);
            return null;
        }
      }));

      const validTasks = tasks.filter(t => t !== null) as { orthoId: number, taskId: string, filename: string }[];

      // 2. Мониторинг прогресса
      await Promise.all(validTasks.map(async (task) => {
          try {
              await pollTask(task.taskId, task.orthoId);
              addLog(`Успешно оптимизирован: ${task.filename}`, 'success');
          } catch (e: any) {
              addLog(`Ошибка оптимизации ${task.filename}: ${e.message}`, 'error');
          }
      }));

      addLog('Процесс оптимизации завершен. Обновление списка...', 'success');
      alert('Оптимизация завершена. Список обновляется...');
      
      setRowProgress({});
      await loadOrthos();

    } catch (error) {
      addLog('Произошла критическая ошибка при массовой оптимизации COG', 'error');
      alert('Произошла ошибка при массовой обработке');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkDownload = () => {
    if (selectedIds.length === 0) return;
    if (selectedIds.length > 5) {
        if (!window.confirm(`Скачать ${selectedIds.length} файлов сразу?`)) return;
    }

    const items = orthos.filter(o => selectedIds.includes(o.id));
    addLog(`Инициировано скачивание ${items.length} файлов`, 'info');
    items.forEach(item => {
        window.open(item.url, '_blank');
    });
  };

  const isGoogleProjection = (crs?: string) => {
    if (!crs) return false;
    return crs.includes('3857') || crs.includes('Pseudo-Mercator') || crs.includes('Google');
  };

  // Стили для логов (встроены для простоты, лучше вынести в CSS)
  const logStyles = {
    container: {
      marginTop: '20px',
      border: '1px solid #ccc',
      borderRadius: '4px',
      backgroundColor: '#1e1e1e',
      color: '#d4d4d4',
      fontFamily: 'monospace',
      fontSize: '12px',
      overflow: 'hidden'
    },
    header: {
      padding: '8px 12px',
      backgroundColor: '#333',
      display: 'flex',
      justifyContent: 'space-between',
      cursor: 'pointer',
      fontWeight: 'bold' as const
    },
    body: {
      padding: '10px',
      maxHeight: '150px',
      overflowY: 'auto' as const
    },
    entry: {
      marginBottom: '4px'
    },
    time: {
      color: '#858585',
      marginRight: '8px'
    },
    info: { color: '#d4d4d4' },
    success: { color: '#4caf50' },
    error: { color: '#f44336' }
  };

  return (
    <div className="table-container" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
      
      {/* 1. ПАНЕЛЬ ДЕЙСТВИЙ (ВСЕГДА ВИДИМА) */}
      <div className="table-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
        
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>


            {/* Кнопки действий */}
            <button 
                className="secondary-button" 
                onClick={handleBulkToggleVisibility}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Переключить видимость для выбранных"
            >
                Видимость
            </button>

            <button 
                className="secondary-button" 
                onClick={handleBulkCreatePreview}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Сгенерировать миниатюру"
            >
                Создать превью
            </button>

            {/* Кнопка конвертации в COG */}
            <button 
                className="secondary-button" 
                onClick={handleBulkProcessCOG}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Оптимизировать в Cloud Optimized GeoTIFF"
            >
                {isProcessing ? 'Wait...' : 'В формат COG'}
            </button>
            
            <button 
                className="secondary-button" 
                onClick={handleBulkReproject}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Конвертировать в EPSG:3857"
            >
                {isProcessing ? 'Wait...' : 'В EPSG:3857'}
            </button>
            
            <button 
                className="secondary-button" 
                onClick={handleBulkDownload}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Скачать"
            >
                Скачать
            </button>
            
            <button 
                className="secondary-button"
                onClick={handleBulkDelete}
                disabled={selectedIds.length === 0 || isProcessing}
                title="Удалить"
            >
                Удалить
            </button>
        </div>

        {/* Группа кнопок справа (Обновить + Загрузить) */}
        <div style={{ display: 'flex', gap: '8px' }}>
            <button 
                className="secondary-button" 
                onClick={loadOrthos}
                disabled={loadingOrthos || isProcessing}
                title="Обновить список из БД"
            >
                {loadingOrthos ? '⏳' : 'Обновить'}
            </button>
            
            <Link to="/uploadortho">
            <button className="primary-button">+ Загрузить</button>
            </Link>
        </div>
      </div>

      {loadingOrthos && <div className="loading-state">Загрузка...</div>}
      
      {errorOrthos && (
        <div className="error-message" style={{ color: 'red', padding: '20px', background: '#ffe6e6', borderRadius: '4px' }}>
          <strong>Ошибка:</strong> {errorOrthos}
        </div>
      )}

      {!loadingOrthos && !errorOrthos && orthos.length === 0 && (
        <div className="empty-state">Нет загруженных ортофотопланов</div>
      )}

      {/* 2. ТАБЛИЦА */}
      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <div style={{ flexGrow: 1, overflow: 'auto' }}>
            <table className="data-table">
            <thead>
                <tr>
                <th style={{ width: '40px', textAlign: 'center' }}>
                    <input 
                        type="checkbox" 
                        checked={selectedIds.length === orthos.length && orthos.length > 0}
                        onChange={handleSelectAll}
                    />
                </th>
                <th>Название</th>
                <th>Превью</th>
                <th>Проекция (CRS)</th>
                <th style={{ textAlign: 'center' }}>COG</th> {/* <--- ДОБАВЛЕНО ---> */}
                <th>Статус / Прогресс</th>
                <th>Границы (W, S, E, N)</th>
                <th style={{ textAlign: 'center' }}>Видимость</th>
                </tr>
            </thead>
            <tbody>
                {orthos.map((ortho) => {
                    // Проверяем, есть ли активный прогресс для этой строки
                    const progress = rowProgress[ortho.id];
                    const hasProgress = progress !== undefined;

                    return (
                    <tr 
                        key={ortho.id} 
                        className={selectedIds.includes(ortho.id) ? 'selected-row' : ''}
                    >
                        <td style={{ textAlign: 'center' }}>
                            <input 
                                type="checkbox" 
                                checked={selectedIds.includes(ortho.id)}
                                onChange={() => handleSelectRow(ortho.id)}
                            />
                        </td>

                        <td style={{maxWidth: '200px', wordBreak: 'break-word'}}>
                            {ortho.filename}
                        </td>
                        
                        <td>
                        <div style={{ width: '100px', height: '60px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#eee', borderRadius: '4px' }}>
                            <img 
                            src={ortho.url} 
                            alt="preview" 
                            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                            onError={(e) => { (e.target as HTMLImageElement).src = NO_IMAGE_PLACEHOLDER; }}
                            />
                        </div>
                        </td>

                        <td>
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
                        </td>

                        {/* <--- ДОБАВЛЕНА ЯЧЕЙКА COG ---> */}
                        <td style={{ textAlign: 'center' }}>
                            {ortho.is_cog ? (
                                <span style={{
                                    display: 'inline-block',
                                    background: '#e6fffa',
                                    color: '#007a5e',
                                    padding: '4px 8px',
                                    borderRadius: '12px',
                                    border: '1px solid #b7eb8f',
                                    fontSize: '0.8em',
                                    fontWeight: 500
                                }}>
                                    Да
                                </span>
                            ) : (
                                <span style={{
                                    display: 'inline-block',
                                    background: '#fff0f6',
                                    color: '#eb2f96',
                                    padding: '4px 8px',
                                    borderRadius: '12px',
                                    border: '1px solid #ffadd2',
                                    fontSize: '0.8em',
                                    fontWeight: 500
                                }}>
                                    Нет
                                </span>
                            )}
                        </td>

                        {/* [MODIFIED] Колонка Статус / Прогресс */}
                        <td style={{ width: '200px' }}>
                            {hasProgress ? (
                                <div style={{ width: '100%' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px', fontSize: '11px' }}>
                                        <span>Обработка...</span>
                                        <span>{progress}%</span>
                                    </div>
                                    <div style={{ width: '100%', height: '8px', background: '#e0e0e0', borderRadius: '4px', overflow: 'hidden' }}>
                                        <div style={{ 
                                            width: `${progress}%`, 
                                            height: '100%', 
                                            background: '#4caf50', 
                                            transition: 'width 0.5s ease-in-out' 
                                        }} />
                                    </div>
                                </div>
                            ) : (
                                <span style={{fontSize:'0.8em', color:'#555'}}>Готов к работе</span>
                            )}
                        </td>

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

                        <td style={{ textAlign: 'center' }}>
                            <input 
                                type="checkbox"
                                checked={visibleIds.includes(ortho.id)}
                                disabled={true} 
                                style={{ cursor: 'not-allowed', opacity: 0.7 }}
                            />
                        </td>
                    </tr>
                    );
                })}
            </tbody>
            </table>
        </div>
      )}

                  {/* Счетчик выделенных */}
            <span style={{ fontSize: '0.9em', fontWeight: 'bold', marginRight: '5px', minWidth: '80px' }}>
                {selectedIds.length > 0 ? `Выбрано: ${selectedIds.length}` : 'Выберите элементы'}
            </span>

      {/* 3. ПАНЕЛЬ ЛОГОВ */}
      <div style={logStyles.container}>
        <div style={logStyles.header} onClick={() => setShowLogs(!showLogs)}>
            <span>Системные логи ({logs.length})</span>
            <span>{showLogs ? '▼' : '▲'}</span>
        </div>
        
        {showLogs && (
            <div style={logStyles.body}>
                {logs.length === 0 ? (
                    <div style={{ color: '#858585', fontStyle: 'italic' }}>Логи пусты. Начните работу с файлами.</div>
                ) : (
                    logs.map(log => (
                        <div key={log.id} style={logStyles.entry}>
                            <span style={logStyles.time}>[{log.time}]</span>
                            <span style={logStyles[log.type]}>{log.message}</span>
                        </div>
                    ))
                )}
                <div ref={logsEndRef} />
            </div>
        )}
      </div>

    </div>
  );
};

export default ProfileOrthophotos;