import React, { useState, useRef } from 'react';
import Header from './Header';

const UploadPage = () => {
  const [files, setFiles] = useState([]);
  const [tags, setTags] = useState([]);
  const [skippedFiles, setSkippedFiles] = useState([]);
  const [logMessages, setLogMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const fileInputRef = useRef(null);

  const onFileChange = (event) => {
    const filteredFiles = Array.from(event.target.files).filter(file => file.type === "image/jpeg");
    if (filteredFiles.length !== event.target.files.length) {
      setLogMessages(prevMessages => [...prevMessages, 'Можно загружать только файлы с расширением .jpg']);
    }
    setFiles(filteredFiles);
  };

  const onInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const onInputKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ',' || event.key === '.') {
      event.preventDefault();
      if (inputValue.trim()) {
        setTags([...tags, inputValue.trim()]);
        setInputValue('');
      }
    }
  };

  const removeTag = (indexToRemove) => {
    setTags(tags.filter((_, index) => index !== indexToRemove));
  };

  const onFileUpload = async () => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append("files", file);
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
      setLogMessages(prevMessages => [
        ...prevMessages,
        `Загрузка завершена. Успешно: ${result.successful_uploads.length}, Ошибок: ${result.failed_uploads.length}`
      ]);
      setSkippedFiles(result.skipped_files || []);
    } catch (error) {
      console.error('Ошибка при загрузке:', error);
      setLogMessages(prevMessages => [...prevMessages, `Произошла ошибка при загрузке файлов: ${error.message}`]);
    }
  };

  const handleFileInputClick = () => {
    fileInputRef.current.click();
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
              rows="1"
              cols="50"
              className="input-tags"
            />
          </div>
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
        </div>
        <button onClick={onFileUpload} className="button">Загрузить</button>
      </div>
    </div>
  );
};

export default UploadPage;
