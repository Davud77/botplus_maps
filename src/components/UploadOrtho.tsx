import React, { useState, useRef, DragEvent } from 'react';
import axios from 'axios';
import '../assets/css/uploadOrtho.css';

interface FileItem {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'failed';
  message?: string;      // сообщение об ошибке или успехе
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
      message: '',
      previewUrl: '' // тут можно сохранить blob-ссылку, если хотите превью
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

    const updatedFiles = [...files];

    for (let i = 0; i < updatedFiles.length; i++) {
      if (updatedFiles[i].status === 'pending') {
        updatedFiles[i].status = 'uploading';
        setFiles([...updatedFiles]); // обновим UI

        const formData = new FormData();
        formData.append('files', updatedFiles[i].file);

        try {
          const response = await axios.post('https://api.botplus.ru/upload_ortho', formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          });
          updatedFiles[i].status = 'success';
          updatedFiles[i].message = response.data?.message || 'Успешно загружен';
        } catch (error: any) {
          updatedFiles[i].status = 'failed';
          updatedFiles[i].message =
            error.response?.data?.error || error.message || 'Ошибка при загрузке';
        }
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
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  };

  return (
    <div className="tag-container">

      <div className="mini">
        {/* Отображение "загружаемых" файлов */}
        <div className={`mini_pano ${isDragging ? 'dragging' : ''}`}>
          <div className="mini_header">
            <h3>Загрузка ортофотопланов</h3>
            <div className="functions">
              <button onClick={() => setFiles([])}>Очистить</button>
              <button onClick={handleUploadAll}>Загрузить все</button>
            </div>
          </div>

          {/* Drag'n'Drop зона */}
          <div
            className="drag-drop-container"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <p>{isDragging ? 'Отпустите файлы здесь' : 'Перетащите файлы .tif или кликните для выбора'}</p>
            <input
              type="file"
              accept=".tif"
              multiple
              onChange={(e) => {
                if (e.target.files) handleFilesAddition(e.target.files);
              }}
              style={{
                position: 'absolute',
                width: '100%',
                height: '100%',
                opacity: 0,
                cursor: 'pointer'
              }}
            />
          </div>

          {/* Список файлов с превью */}
          {files.map((item, idx) => (
            <div
              key={idx}
              className={`thumbnail ${item.status}`}
              style={{ justifyContent: 'space-between', alignItems: 'center' }}
            >
              <div style={{ display: 'flex', alignItems: 'center' }}>
                {item.previewUrl ? (
                  <img src={item.previewUrl} alt="" className="thumbnail-image" />
                ) : (
                  <div className="thumbnail-image" style={{ background: '#f1f1f1' }}>
                    {/* Место для "placeholder" */}
                  </div>
                )}
                <div className="thumbnail-name">
                  {item.file.name}
                  <div style={{ fontSize: '12px' }}>
                    {(item.file.size / 1024 / 1024).toFixed(2)} MB
                  </div>
                </div>
              </div>
              
              <div>
                {/* Кнопка для удаления из очереди */}
                <button onClick={() => handleRemoveFile(idx)}>X</button>
              </div>
            </div>
          ))}
        </div>

        {/* Лог загрузок */}
        <div className="mini_log" ref={logRef}>
          <ul>
            {files
              .filter((f) => f.status !== 'pending')
              .map((f, idx) => (
                <li key={idx}>
                  [{f.status.toUpperCase()}] {f.file.name}: {f.message}
                </li>
              ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default UploadOrtho;