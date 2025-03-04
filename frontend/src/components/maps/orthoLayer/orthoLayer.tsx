import React, { useState } from 'react';

/** Единый интерфейс для ортофото, 
 *  соответствующий данным с бэкенда (id, filename, url, bounds).
 */
export interface OrthoImageType {
  id: number;
  filename: string;   // бэкенд возвращает
  url: string;        // ссылка на превью
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
}

interface OrthoLayerProps {
  // Родительский компонент передаёт функцию, 
  // которая включит/выключит слой орто и покажет панель
  toggleOrthoLayer: (orthoList: OrthoImageType[]) => void;
}

const OrthoLayer: React.FC<OrthoLayerProps> = ({ toggleOrthoLayer }) => {
  const [orthoImages, setOrthoImages] = useState<OrthoImageType[]>([]);

  // При клике на кнопку "Показать орто" запрашиваем данные и передаём их в родителя
  const handleToggle = async () => {
    try {
      const response = await fetch('https://api.botplus.ru/orthophotos');
      if (!response.ok) {
        throw new Error('Ошибка при загрузке ортофото: ' + response.status);
      }
      const data: OrthoImageType[] = await response.json();
      setOrthoImages(data);

      // Передаём список в родитель, чтобы там открыть/закрыть панель и слой
      toggleOrthoLayer(data);
    } catch (error) {
      console.error('Ошибка при загрузке ортофото:', error);
    }
  };

  return (
    <button 
      className="ortho-toggle-button"
      onClick={handleToggle}
    >
      Показать орто
    </button>
  );
};

export default OrthoLayer;