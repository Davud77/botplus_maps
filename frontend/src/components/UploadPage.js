import React, { useState, useRef } from 'react';
import Header from './Header';

const UploadPage = () => {
  const [files, setFiles] = useState([]);
  const [tags, setTags] = useState('');
  const [skippedFiles, setSkippedFiles] = useState([]);
  const [logMessages, setLogMessages] = useState([]);
  const fileInputRef = useRef(null);

  const onFileChange = (event) => {
    const filteredFiles = Array.from(event.target.files).filter(file => file.type === "image/jpeg");
    if (filteredFiles.length !== event.target.files.length) {
      setLogMessages(prevMessages => [...prevMessages, 'Можно загружать только файлы с расширением .jpg']);
    }
    setFiles(filteredFiles);
  };

  const onTagsChange = (event) => {
    setTags(event.target.value);
  };

  const onFileUpload = async () => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append("files", file);
    });
    formData.append("tags", tags);

    try {
      const response = await fetch('https://api.botplus.ru/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      setLogMessages(prevMessages => [
        ...prevMessages,
        `Загрузка завершена. Успешно: ${result.successful_uploads.length}, Ошибок: ${result.failed_uploads.length}`
      ]);
      setSkippedFiles(result.skipped_files || []);
    } catch (error) {
      console.error('Ошибка при загрузке:', error);
      setLogMessages(prevMessages => [...prevMessages, 'Произошла ошибка при загрузке файлов.']);
    }
  };

  const handleFileInputClick = () => {
    fileInputRef.current.click();
  };

  return (
    <div className="background">
      <Header />
      <div className="centered-container">
        <div className="upload_container">
          <h1>Массовая загрузка панорам</h1>
          <textarea
            value={tags}
            onChange={onTagsChange}
            placeholder="Введите теги через запятую"
            rows="4"
            cols="50"
            className="input-tags"
          />
          <div className="button-container">
            <input
              type="file"
              multiple
              accept=".jpg"
              onChange={onFileChange}
              ref={fileInputRef}
              style={{ display: 'none' }}
            />
            <button className="button" onClick={handleFileInputClick}>Выбрать файлы</button>
            <button onClick={onFileUpload} className="button">Загрузить</button>
          </div>
        </div>
        <div className="mini">
          <h1>Выбранные файлы</h1>
          <div className="mini_pano">
            {files.map((file, index) => (
              <div key={index} className="thumbnail">
                <img
                  src={URL.createObjectURL(file)}
                  alt={file.name}
                  className="thumbnail-image"
                />
                <p className="thumbnail-name">{file.name}</p>
              </div>
            ))}
          </div>
          <h1>Логи загрузки</h1>
          <div className="mini_log">
            {logMessages.length > 0 && (
              <div>
                <ul>
                  {logMessages.map((message, index) => (
                    <li key={index}>{message}</li>
                  ))}
                </ul>
              </div>
            )}
            {skippedFiles.length > 0 && (
              <div>
                <h2>Пропущенные файлы:</h2>
                <ul>
                  {skippedFiles.map((file, index) => (
                    <li key={index}>{file}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
