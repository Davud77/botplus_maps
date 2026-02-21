// src/components/UploadOrtho.tsx
import React, { useState, useRef, useEffect, DragEvent } from 'react';
import Header from './Header';

// Определение адреса API для разработки
const isLocalhost = 
  typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
const API_URL = isLocalhost ? 'http://localhost:5580' : '';

interface FileItem {
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'success' | 'failed';
  progress: number;
  message?: string;
}

interface LogEntry {
  time: string;
  text: string;
  type: 'info' | 'success' | 'error' | 'warning';
}

const UploadOrtho: React.FC = () => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [globalLogs, setGlobalLogs] = useState<LogEntry[]>([]);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  
  const logRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const addLog = (text: string, type: LogEntry['type'] = 'info') => {
    const time = new Date().toLocaleTimeString('ru-RU');
    setGlobalLogs(prev => [...prev, { time, text, type }]);
  };

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [globalLogs]);

  // --- Управление файлами ---
  const handleFilesAddition = (newFiles: FileList) => {
    const validFiles: FileItem[] = Array.from(newFiles).map((f) => ({
      file: f,
      status: 'pending',
      progress: 0,
      message: 'Ожидает очереди',
    }));
    setFiles((prev) => [...prev, ...validFiles]);
    addLog(`Добавлено файлов в очередь: ${validFiles.length}`);
  };

  const handleContainerClick = () => {
    fileInputRef.current?.click();
  };

  // --- Drag'n'Drop ---
  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(true);
  };
  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
  };
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
    if (e.dataTransfer?.files?.length) handleFilesAddition(e.dataTransfer.files);
  };

  // --- Опрос бэкенда (Поллинг) ---
  const pollUploadTask = (taskId: string, index: number, filename: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      let errorCount = 0; // [NEW] Счетчик ошибок для защиты от бесконечного цикла

      const interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/api/tasks/${taskId}`);
          
          if (!response.ok) {
              if (response.status === 404) throw new Error('404');
              throw new Error('Network error during polling');
          }
          
          const statusData = await response.json();
          errorCount = 0; // Сбрасываем счетчик при успешном ответе

          if (statusData.status === 'processing' || statusData.status === 'pending') {
            setFiles(prev => prev.map((item, i) => {
              if (i !== index) return item;
              // Вторые 50% прогресс-бара — это работа сервера
              const backendProgress = statusData.progress || 0;
              const totalProgress = Math.round(50 + (backendProgress / 2));
              
              return { 
                ...item, 
                status: 'processing', 
                progress: totalProgress, 
                message: statusData.message || 'Обработка...' 
              };
            }));
          } else if (statusData.status === 'success') {
            clearInterval(interval);
            setFiles(prev => prev.map((item, i) => 
              i === index ? { ...item, status: 'success', progress: 100, message: 'Готово' } : item
            ));
            addLog(`[${filename}] Успешно обработан!`, 'success');
            resolve();
          } else if (statusData.status === 'error') {
            clearInterval(interval);
            setFiles(prev => prev.map((item, i) => 
              i === index ? { ...item, status: 'failed', message: 'Ошибка обработки' } : item
            ));
            addLog(`[ERROR] ${filename}: ${statusData.error}`, 'error');
            reject(new Error(statusData.error));
          }
        } catch (e: any) {
          console.error("Polling error", e);
          errorCount++;
          
          // [NEW] Обрываем цикл при 404 или множестве ошибок сети
          if ((e.message && e.message.includes('404')) || errorCount > 10) {
             clearInterval(interval);
             setFiles(prev => prev.map((item, i) => 
               i === index ? { ...item, status: 'failed', message: 'Сбой соединения с сервером' } : item
             ));
             addLog(`[ERROR] ${filename}: Задача прервана сервером (перезагрузка?)`, 'error');
             reject(new Error('Task lost on server'));
          }
        }
      }, 1500); 
    });
  };

  // --- Загрузка файла ---
  const uploadSingleFile = (index: number, fileItem: FileItem) => {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('files', fileItem.file);

      // 1. Прогресс загрузки по сети
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setFiles(prev => prev.map((item, i) => {
            if (i !== index) return item;
            // Делим прогресс: первые 50% — это передача файла
            return { 
              ...item, 
              status: 'uploading', 
              progress: Math.round(percentComplete / 2), 
              message: `Передача: ${percentComplete}%` 
            };
          }));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            
            // Если сервер вернул task_id, запускаем опрос
            if (response.task_id) {
              addLog(`[${fileItem.file.name}] Файл загружен. Запущена обработка на сервере...`, 'info');
              
              setFiles(prev => prev.map((item, i) => 
                i === index ? { ...item, status: 'processing', progress: 50, message: 'Ожидание сервера...' } : item
              ));
              
              // Начинаем поллинг задачи
              pollUploadTask(response.task_id, index, fileItem.file.name)
                .then(resolve)
                .catch(reject);
            } else {
              // Фоллбэк, если бэкенд отработал моментально
              setFiles(prev => prev.map((item, i) => 
                i === index ? { ...item, status: 'success', progress: 100, message: 'Готово' } : item
              ));
              addLog(`[${fileItem.file.name}] Успешно обработан.`, 'success');
              resolve();
            }
          } catch (e) {
            addLog(`[${fileItem.file.name}] Ошибка парсинга ответа сервера`, 'error');
            reject(e);
          }
        } else {
          addLog(`[${fileItem.file.name}] Ошибка сервера: ${xhr.status} ${xhr.statusText}`, 'error');
          reject(new Error(xhr.statusText));
        }
      };

      xhr.onerror = () => {
        addLog(`[${fileItem.file.name}] Сетевая ошибка`, 'error');
        reject(new Error('Network Error'));
      };

      addLog(`[${fileItem.file.name}] Начало передачи...`, 'info');
      setFiles(prev => prev.map((item, i) => 
        i === index ? { ...item, status: 'uploading', message: 'Подключение...' } : item
      ));

      xhr.open('POST', `${API_URL}/api/upload_ortho`);
      // xhr.withCredentials = true; // Раскомментируй, если используются сессии/куки для авторизации при загрузке
      xhr.send(formData);
    });
  };

  const handleUploadAll = async () => {
    if (files.length === 0) return;
    const indicesToUpload = files
      .map((f, index) => (f.status === 'pending' || f.status === 'failed' ? index : -1))
      .filter(i => i !== -1);

    if (indicesToUpload.length === 0) {
      addLog('Нет файлов для загрузки', 'warning');
      return;
    }
    addLog(`Запуск пакетной загрузки: ${indicesToUpload.length} файлов`, 'info');
    
    // Запускаем файлы по очереди, чтобы не перегружать сеть и сервер
    for (const index of indicesToUpload) {
      try {
        await uploadSingleFile(index, files[index]);
      } catch (error: any) {
        setFiles(prev => prev.map((item, i) => 
          i === index ? { ...item, status: 'failed', message: 'Ошибка' } : item
        ));
        addLog(`[ERROR] ${files[index].file.name}: ${error.message || 'Unknown error'}`, 'error');
      }
    }
    addLog('Пакетная обработка завершена', 'info');
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== index));
  };

  return (
    <div className="contend">
      <Header />
      <div className="tag-container">
        <div className="mini">
          <div className={`mini_pano ${isDragging ? 'dragging' : ''}`}>
            
            <div className="mini_header">
              <h3>Загрузка ортофотопланов (GeoTIFF)</h3>
              <div className="functions">
                <button onClick={(e) => { e.stopPropagation(); setFiles([]); setGlobalLogs([]); }} className="secondary-button">Очистить</button>
                <button onClick={(e) => { e.stopPropagation(); handleUploadAll(); }} className="primary-button">Загрузить все</button>
              </div>
            </div>

            {/* Зона загрузки */}
            <div
              className="drag-drop-container"
              onClick={handleContainerClick}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {files.length === 0 && (
                <div className="drag-drop-placeholder">
                   {isDragging ? 'Отпустите файлы здесь' : 'Перетащите .tif файлы или нажмите для выбора'}
                </div>
              )}
              
              {/* Скрытый инпут */}
              <input 
                ref={fileInputRef}
                type="file"
                accept=".tif,.tiff"
                multiple
                onChange={(e) => { if (e.target.files) handleFilesAddition(e.target.files); }}
                style={{ display: 'none' }}
              />

              <div className="file-list">
                {files.map((item, idx) => (
                  <div key={idx} className="thumbnail" onClick={(e) => e.stopPropagation()}>
                    
                    {/* Показываем прогресс-бар и для загрузки по сети, и для фоновой обработки */}
                    {(item.status === 'uploading' || item.status === 'processing') && (
                       <div className="progress-line" style={{ width: `${item.progress}%` }} />
                    )}

                    <div className={`file-icon ${item.status}`}>
                        {item.status === 'success' ? '✅' : (item.status === 'failed' ? '❌' : '📄')}
                    </div>

                    <div className="file-info">
                      <div className="file-name">{item.file.name}</div>
                      <div className="file-meta">
                         <span>{(item.file.size / 1024 / 1024).toFixed(2)} MB</span>
                         <span className={`file-status ${item.status}`}>{item.message}</span>
                      </div>
                    </div>

                    {/* Скрываем кнопку удаления во время активного процесса */}
                    {item.status !== 'uploading' && item.status !== 'processing' && (
                        <button 
                            className="btn-remove"
                            onClick={(e) => { 
                                e.stopPropagation(); 
                                handleRemoveFile(idx); 
                            }}
                        >
                        &times;
                        </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="log-terminal" ref={logRef}>
            <div className="log-prompt">root@console: ~/upload_logs $</div>
            {globalLogs.map((log, idx) => (
              <div key={idx} className="log-entry">
                <span className="log-time">[{log.time}]</span>
                <span className={`log-text ${log.type}`}>{log.text}</span>
              </div>
            ))}
          </div>

        </div>
      </div>
    </div>
  );
};

export default UploadOrtho;