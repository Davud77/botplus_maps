import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import Header from './Header'; // Импортируем Header

const UploadPage = () => {
  const [files, setFiles] = useState([]);
  const [tags, setTags] = useState('');
  const fileInputRef = useRef(null);

  const onFileChange = (event) => {
    setFiles([...event.target.files]);
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
      const response = await fetch('http://localhost:5000/upload', {
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
          <input type="file" multiple onChange={onFileChange} ref={fileInputRef} style={{ display: 'none' }} />
          <button className="button" onClick={handleFileInputClick}>Выбрать файлы</button>
          <button onClick={onFileUpload} className="button">Загрузить</button>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
