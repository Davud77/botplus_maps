// src/components/UploadOrtho.tsx
import React, { useState, useRef, useEffect, DragEvent } from 'react';
import Header from './Header';

// ... (API_URL и интерфейсы остались без изменений) ...
const API_URL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:5580' 
  : '';

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
  // 1. Создаем реф для скрытого инпута
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // ... (addLog и useEffect для логов без изменений) ...
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

  // 2. Обработчик клика по контейнеру
  const handleContainerClick = () => {
    // Программно кликаем по скрытому инпуту
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

  // ... (uploadSingleFile и handleUploadAll без изменений) ...
  const uploadSingleFile = (index: number, fileItem: FileItem) => {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('files', fileItem.file);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setFiles(prev => prev.map((item, i) => {
            if (i !== index) return item;
            return { ...item, status: 'uploading', progress: percentComplete, message: `Загрузка: ${percentComplete}%` };
          }));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            setFiles(prev => prev.map((item, i) => 
              i === index ? { ...item, status: 'success', progress: 100, message: 'Готово' } : item
            ));
            addLog(`[${fileItem.file.name}] Успешно обработан.`, 'success');
            if (response.logs && Array.isArray(response.logs)) {
              response.logs.forEach((logLine: string) => {
                addLog(`[SERVER] ${fileItem.file.name}: ${logLine}`, 'info');
              });
            }
            resolve();
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

      addLog(`[${fileItem.file.name}] Начало загрузки...`, 'info');
      setFiles(prev => prev.map((item, i) => 
        i === index ? { ...item, status: 'uploading', message: 'Начало передачи...' } : item
      ));

      xhr.open('POST', `${API_URL}/api/upload_ortho`);
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

            {/* Зона загрузки: Клик по ней вызывает инпут */}
            <div
              className="drag-drop-container"
              onClick={handleContainerClick} // <--- ВАЖНО: Клик по всей зоне
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
                style={{ display: 'none' }} // <--- ВАЖНО: Скрыт
              />

              <div className="file-list">
                {files.map((item, idx) => (
                  <div key={idx} className="thumbnail" onClick={(e) => e.stopPropagation() /* Чтобы клик по файлу не открывал диалог снова (опционально) */ }>
                    
                    {item.status === 'uploading' && (
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

                    {item.status !== 'uploading' && item.status !== 'processing' && (
                        <button 
                            className="btn-remove"
                            onClick={(e) => { 
                                e.stopPropagation(); // <--- ВАЖНО: Остановить всплытие, иначе откроется окно выбора
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