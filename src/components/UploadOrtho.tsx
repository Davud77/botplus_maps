// src/components/UploadOrtho.tsx
import React, { useState, useRef, DragEvent } from 'react';
// [FIX] Используем нашу функцию API вместо прямого axios
import { uploadOrthoFiles } from '../utils/api';

interface FileItem {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'failed';
  message?: string;      // сообщение об ошибке или успехе
  logs?: string[];       // детальные логи от бэкенда
  previewUrl?: string;   // можно подставить ссылку на preview
}

const UploadOrtho: React.FC = () => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const logRef = useRef<HTMLDivElement | null>(null); // для скролла лога

  // Добавляем файлы в список (без загрузки)
  const handleFilesAddition = (newFiles: FileList) => {
    const validFiles: FileItem[] = Array.from(newFiles).map((f) => ({
      file: f,
      status: 'pending',
      message: 'Ожидает загрузки...',
      previewUrl: '' 
    }));
    setFiles((prev) => [...prev, ...validFiles]);
  };

  // Drag'n'Drop events
  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer?.files?.length) {
      handleFilesAddition(e.dataTransfer.files);
    }
  };

  // Загрузка всех добавленных файлов
  const handleUploadAll = async () => {
    if (files.length === 0) return;

    // Создаем копию массива для мутаций статусов
    const updatedFiles = [...files];

    // Проходим по файлам и загружаем только "pending"
    for (let i = 0; i < updatedFiles.length; i++) {
      if (updatedFiles[i].status === 'pending') {
        
        // Ставим статус "Загрузка"
        updatedFiles[i].status = 'uploading';
        updatedFiles[i].message = 'Загрузка и обработка (GDAL)...';
        setFiles([...updatedFiles]); // Обновляем UI

        const formData = new FormData();
        // Бэкенд ожидает поле 'files'
        formData.append('files', updatedFiles[i].file);

        try {
          // [FIX] Вызываем api.ts (автоматически подставит правильный хост и /api/upload_ortho)
          const response = await uploadOrthoFiles(formData);
          
          updatedFiles[i].status = 'success';
          updatedFiles[i].message = response.message || 'Успешно загружен и обработан';
          // Если бэкенд возвращает логи обработки, сохраним их
          if (response.logs && Array.isArray(response.logs)) {
             updatedFiles[i].logs = response.logs;
          }

        } catch (error: any) {
          console.error(`Ошибка загрузки файла ${updatedFiles[i].file.name}:`, error);
          updatedFiles[i].status = 'failed';
          updatedFiles[i].message = error.message || 'Ошибка при загрузке';
        }
        
        // Обновляем состояние после завершения (успех или ошибка)
        setFiles([...updatedFiles]);
        scrollLogToBottom();
      }
    }
  };

  // Удаляем файл из списка
  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== index));
  };

  // Прокрутить лог вниз
  const scrollLogToBottom = () => {
    // Небольшая задержка, чтобы DOM успел обновиться
    setTimeout(() => {
        if (logRef.current) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
        }
    }, 100);
  };

  return (
    <div className="tag-container">

      <div className="mini">
        {/* Отображение "загружаемых" файлов */}
        <div className={`mini_pano ${isDragging ? 'dragging' : ''}`} style={{ minHeight: '300px', display: 'flex', flexDirection: 'column' }}>
          <div className="mini_header">
            <h3>Загрузка ортофотопланов (GeoTIFF)</h3>
            <div className="functions">
              <button onClick={() => setFiles([])} className="secondary-button">Очистить</button>
              <button onClick={handleUploadAll} className="primary-button">Загрузить все</button>
            </div>
          </div>

          {/* Drag'n'Drop зона */}
          <div
            className="drag-drop-container"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{ flex: 1, position: 'relative', border: '2px dashed #ccc', margin: '10px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: isDragging ? '#eeffff' : 'transparent' }}
          >
            {files.length === 0 && (
                <p style={{pointerEvents: 'none', color: '#888'}}>
                    {isDragging ? 'Отпустите файлы здесь' : 'Перетащите файлы .tif или кликните для выбора'}
                </p>
            )}
            
            <input
              type="file"
              accept=".tif,.tiff"
              multiple
              onChange={(e) => {
                if (e.target.files) handleFilesAddition(e.target.files);
              }}
              style={{
                position: 'absolute',
                width: '100%',
                height: '100%',
                opacity: 0,
                cursor: 'pointer',
                top: 0,
                left: 0
              }}
            />

            {/* Список файлов внутри дропзоны или под ней, как удобнее. 
                В вашем дизайне список был внутри mini_pano, рендерим его поверх инпута (с pointer-events на кнопках) 
            */}
            {files.length > 0 && (
                <div className="file-list-overlay" style={{ 
                    position: 'absolute', 
                    top: 0, 
                    left: 0, 
                    width: '100%', 
                    height: '100%', 
                    overflowY: 'auto', 
                    padding: '10px', 
                    zIndex: 2,
                    pointerEvents: 'none' // Чтобы клики проходили сквозь пустое место к инпуту
                }}>
                    {files.map((item, idx) => (
                        <div
                        key={idx}
                        className={`thumbnail ${item.status}`}
                        style={{ 
                            justifyContent: 'space-between', 
                            alignItems: 'center', 
                            background: 'white', 
                            marginBottom: '5px', 
                            padding: '10px',
                            borderRadius: '4px',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                            pointerEvents: 'auto' // Вернуть клики элементам списка
                        }}
                        >
                        <div style={{ display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
                            <div className="thumbnail-icon" style={{ 
                                width: '40px', 
                                height: '40px', 
                                background: item.status === 'success' ? '#e6fffa' : '#eee', 
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                marginRight: '10px',
                                borderRadius: '4px',
                                fontSize: '20px'
                            }}>
                                {item.status === 'success' ? '✅' : '🗺️'}
                            </div>
                            <div className="thumbnail-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            <div style={{fontWeight: 'bold'}}>{item.file.name}</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>
                                {(item.file.size / 1024 / 1024).toFixed(2)} MB — {item.message}
                            </div>
                            </div>
                        </div>
                        
                        <div>
                            {/* Кнопка для удаления из очереди (если еще не загружается) */}
                            {item.status !== 'uploading' && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleRemoveFile(idx); }}
                                    style={{ background: 'transparent', color: 'red', border: 'none', cursor: 'pointer', fontSize: '16px' }}
                                >
                                &times;
                                </button>
                            )}
                        </div>
                        </div>
                    ))}
                </div>
            )}
          </div>
        </div>

        {/* Лог загрузок (технический) */}
        <div className="mini_log" ref={logRef} style={{ marginTop: '10px', maxHeight: '200px', overflowY: 'auto', background: '#222', color: '#0f0', padding: '10px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '12px' }}>
          <div>--- Лог операций ---</div>
          {files.flatMap((f) => {
              if (!f.logs) return [];
              return f.logs.map(l => `[${f.file.name}] ${l}`);
          }).map((logLine, idx) => (
              <div key={idx}>{logLine}</div>
          ))}
          {files.map((f, idx) => (
              (f.status === 'failed') ? <div key={`err-${idx}`} style={{color: 'red'}}>[ERROR] {f.file.name}: {f.message}</div> : null
          ))}
        </div>
      </div>
    </div>
  );
};

export default UploadOrtho;