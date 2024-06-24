import React from 'react';

const PointInfo = ({ data }) => {
  if (!data) {
    return <div>Loading...</div>;
  }

  return (
    <div className="layers-menu">
      <h2>Информация о точке</h2>
      <p>Название файла: {data.filename}</p>
      <p>Широта: {data.latitude}</p>
      <p>Долгота: {data.longitude}</p>
      <p>Теги: {data.tags}</p>
      <p>Дата загрузки: {data.upload_date}</p>
      <p>Пользователь: {data.user_id}</p>
      <p>Размер файла: {data.file_size} MB</p>
      <p>Тип файла: {data.file_type}</p>
      <p>Ширина панорамы: {data.full_pano_width_pixels} пикселей</p>
      <p>Высота панорамы: {data.full_pano_height_pixels} пикселей</p>
      <p>Дата первой фотографии: {data.first_photo_date}</p>
      <p>Модель камеры: {data.model}</p>
      <p>Высота GPS: {data.gps_altitude}</p>
      <p>Поле зрения: {data.fov} градусов</p>
    </div>
  );
};

export default PointInfo;
