// src/components/UploadPano.tsx
import React, { useState, useRef, ChangeEvent, KeyboardEvent, DragEvent } from 'react';
import Header from './Header';

interface FileStatus {
  status: 'selected' | 'uploading' | 'success' | 'failed';
  log: string;
}

interface FileStatuses {
  [key: string]: FileStatus;
}

type FilterType = 'all' | 'success' | 'failed' | 'selected';

const UploadPano: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [fileStatuses, setFileStatuses] = useState<FileStatuses>({});
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [filter, setFilter] = useState<FilterType>('all');

  const BATCH_SIZE = 50;

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(event.target.files ?? []).filter((file): file is File => file.type === "image/jpeg");
    if (newFiles.length !== (event.target.files?.length ?? 0)) {
      alert('Можно загружать только файлы с расширением .jpg');
    }
    setFiles(prevFiles => [...prevFiles, ...newFiles]);
    setFileStatuses(prevStatuses => {
      const newStatuses: FileStatuses = {};
      newFiles.forEach(file => {
        newStatuses[file.name] = { status: 'selected', log: '' };
      });
      return { ...prevStatuses, ...newStatuses };
    });
  };

  const onInputChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(event.target.value);
  };

  const onInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' || event.key === ',' || event.key === '.') {
      event.preventDefault();
      if (inputValue.trim()) {
        setTags([...tags, inputValue.trim()]);
        setInputValue('');
      }
    }
  };

  const removeTag = (indexToRemove: number) => {
    setTags(tags.filter((_, index) => index !== indexToRemove));
  };

  const uploadFilesBatch = async (batch: File[]) => {
    const formData = new FormData();
    batch.forEach(file => {
      formData.append("files", file);
      setFileStatuses(prevStatuses => ({
        ...prevStatuses,
        [file.name]: { status: 'uploading', log: 'Загрузка в Minio...' }
      }));
    });
    formData.append("tags", tags.join(', '));

    try {
      const response = await fetch('https://api.botplus.ru/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      result.successful_uploads.forEach((filename: string) => {
        setFileStatuses(prevStatuses => ({
          ...prevStatuses,
          [filename]: { status: 'success', log: 'Успешно загружен' }
        }));
      });
      result.failed_uploads.forEach((filename: string, index: number) => {
        setFileStatuses(prevStatuses => ({
          ...prevStatuses,
          [filename]: { status: 'failed', log: result.skipped_files[index] }
        }));
      });
    } catch (error: any) {
      console.error('Ошибка при загрузке:', error);
      batch.forEach(file => {
        setFileStatuses(prevStatuses => ({
          ...prevStatuses,
          [file.name]: { status: 'failed', log: `Произошла ошибка при загрузке файлов: ${error.message}` }
        }));
      });
    }
  };

  const onFileUpload = async () => {
    const batches: File[][] = [];
    for (let i = 0; i < files.length; i += BATCH_SIZE) {
      batches.push(files.slice(i, i + BATCH_SIZE));
    }

    for (const batch of batches) {
      await uploadFilesBatch(batch);
    }
  };

  const handleFileInputClick = () => {
    fileInputRef.current?.click();
  };

  const getThumbnailClass = (status: string | undefined) => {
    switch (status) {
      case 'selected':
        return 'thumbnail';
      case 'uploading':
        return 'thumbnail uploading';
      case 'success':
        return 'thumbnail success';
      case 'failed':
        return 'thumbnail failed';
      default:
        return 'thumbnail';
    }
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const newFiles = Array.from(event.dataTransfer.files).filter((file): file is File => file.type === "image/jpeg");
    if (newFiles.length !== event.dataTransfer.files.length) {
      alert('Можно загружать только файлы с расширением .jpg');
    }
    setFiles(prevFiles => [...prevFiles, ...newFiles]);
    setFileStatuses(prevStatuses => {
      const newStatuses: FileStatuses = {};
      newFiles.forEach(file => {
        newStatuses[file.name] = { status: 'selected', log: '' };
      });
      return { ...prevStatuses, ...newStatuses };
    });
  };

  const filteredFiles = files.filter(file => {
    if (filter === 'all') return true;
    if (filter === 'success') return fileStatuses[file.name]?.status === 'success';
    if (filter === 'failed') return fileStatuses[file.name]?.status === 'failed';
    if (filter === 'selected') return fileStatuses[file.name]?.status === 'selected';
    return true;
  });

  const clearFiles = () => {
    setFiles([]);
    setFileStatuses({});
  };

  const countFilesByStatus = (status: string) => {
    return files.filter(file => fileStatuses[file.name]?.status === status).length;
  };

  return (
    <div className="contend">
      <Header />
      <div className="centered-container">
        <div className="tag-container">
          <h1>Массовая загрузка панорам</h1>
          <div className="tags-input-container">
            {tags.map((tag, index) => (
              <div key={index} className="tag-item">
                <span>{tag}</span>
                <button onClick={() => removeTag(index)}>x</button>
              </div>
            ))}
            <textarea
              value={inputValue}
              onChange={onInputChange}
              onKeyDown={onInputKeyDown}
              placeholder={tags.length === 0 && inputValue.length === 0 ? "Введите теги через запятую" : ""}
              rows={1}
              cols={50}
              className="input-tags"
            />
          </div>
        </div>
        <div
          className={`mini_pano ${isDragging ? 'dragging' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            multiple
            accept=".jpg"
            onChange={onFileChange}
            ref={fileInputRef}
            style={{ display: 'none' }}
          />
          {files.length === 0 ? (
            <div className="drag-drop-container" onClick={handleFileInputClick}>
              <p>Перетащите файлы сюда или нажмите для выбора файлов</p>
            </div>
          ) : (
            <>
              <div className="mini_header">
                <div className="filters">
                  <button onClick={() => setFilter('all')} className="button_white">Все ({files.length})</button>
                  <button onClick={() => setFilter('success')} className="button_white">Успешно ({countFilesByStatus('success')})</button>
                  <button onClick={() => setFilter('failed')} className="button_white">Ошибки ({countFilesByStatus('failed')})</button>
                  <button onClick={() => setFilter('selected')} className="button_white">Без статуса ({countFilesByStatus('selected')})</button>
                </div>
                <div className="functions">
                  <button onClick={handleFileInputClick} className="button_white">Добавить файлы</button>
                  <button onClick={clearFiles} className="button_white">Очистить список</button>
                </div>
              </div>
              {filteredFiles.map((file, index) => (
                <div key={index} className={getThumbnailClass(fileStatuses[file.name]?.status)}>
                  <img
                    src={URL.createObjectURL(file)}
                    alt={file.name}
                    className="thumbnail-image"
                  />
                  <div>
                    <p className="thumbnail-name">{file.name}</p>
                    <p className="thumbnail-log">{fileStatuses[file.name]?.log}</p>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
        {files.length > 0 && (
          <button onClick={onFileUpload} className="button">Загрузить</button>
        )}
      </div>
    </div>
  );
};

export default UploadPano;