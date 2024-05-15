import React, { useState, useRef } from 'react';
import Header from './Header'; // Импортируем Header

const UploadPage = () => {
  const [files, setFiles] = useState([]);
  const [tags, setTags] = useState('');
  const fileInputRef = useRef(null);

  const onFileChange = (event) => {
    // Фильтрация выбранных файлов, чтобы включать только .jpg
    const filteredFiles = Array.from(event.target.files).filter(file => file.type === "image/jpeg");
    if(filteredFiles.length !== event.target.files.length) {
      alert('Можно загружать только файлы с расширением .jpg');
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
      alert(`Загрузка завершена. Успешно: ${result.successful_uploads}, Ошибок: ${result.failed_uploads}`);
    } catch (error) {
      console.error('Ошибка при загрузке:', error);
      alert('Произошла ошибка при загрузке файлов.');
    }
  };

  const handleFileInputClick = () => {
    fileInputRef.current.click();
  };

  return (
    <div className="background">
      <Header /> {/* Добавляем Header в начало страницы */}
      <div className="centered-container">
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
    </div>
  );
};

export default UploadPage;
