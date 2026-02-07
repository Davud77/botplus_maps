import React, { useRef, useEffect, useState } from 'react';
// @ts-ignore
import Marzipano from 'marzipano';

interface PanoramaViewerProps {
  markerId: string;
  isExpanded: boolean;
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);
  const [pointData, setPointData] = useState<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Обработчик полноэкранного режима
  const toggleFullscreen = () => {
    if (viewerRef.current) {
      if (!isFullscreen) {
        if (viewerRef.current.requestFullscreen) {
          viewerRef.current.requestFullscreen();
        }
        // @ts-ignore
        else if (viewerRef.current.webkitRequestFullscreen) {
          // @ts-ignore
          viewerRef.current.webkitRequestFullscreen();
        }
        setIsFullscreen(true);
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        }
        // @ts-ignore
        else if (document.webkitExitFullscreen) {
          // @ts-ignore
          document.webkitExitFullscreen();
        }
        setIsFullscreen(false);
      }
    }
  };

  // Слушатель изменения полноэкранного режима
  useEffect(() => {
    const handleFullscreenChange = () => {
      // @ts-ignore
      setIsFullscreen(!!document.fullscreenElement || !!document.webkitFullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Инициализация Marzipano и загрузка данных
  useEffect(() => {
    let objectUrl: string | null = null;
    let currentViewer: any = null;
    let isMounted = true; // Флаг для предотвращения обновлений на размонтированном компоненте

    const initializeViewer = async () => {
      if (!markerId) return;
      setError(null);

      try {
        // --- 1. Получаем метаданные (через ПРОКСИ) ---
        // Было: https://api.botplus.ru/pano_info/...
        // Стало: /pano_info/...
        const infoResponse = await fetch(`/pano_info/${markerId}`);
        
        if (!infoResponse.ok) {
           throw new Error(`Ошибка загрузки инфо: ${infoResponse.status}`);
        }
        
        const data = await infoResponse.json();
        if (isMounted) setPointData(data);

        // --- 2. Получаем изображение (через ПРОКСИ) ---
        const imageResponse = await fetch(`/pano_info/${markerId}/download`);
        
        if (!imageResponse.ok) {
            throw new Error(`Ошибка загрузки изображения: ${imageResponse.status}`);
        }

        const blob = await imageResponse.blob();
        if (!isMounted) return;

        objectUrl = URL.createObjectURL(blob);

        // --- 3. Инициализируем просмотрщик ---
        if (viewerRef.current) {
          // Если Marzipano уже был создан, его нужно уничтожить или очистить контейнер
          // Простой способ очистки:
          if (viewerInstanceRef.current) {
             // Marzipano не имеет чистого метода destroy, но мы можем пересоздать viewer 
             // или просто обновить сцену, но для надежности лучше так:
             viewerRef.current.innerHTML = ''; 
          }

          // Создаем Viewer
          currentViewer = new Marzipano.Viewer(viewerRef.current, {
            stage: { progressive: true },
            controls: { mouseViewMode: 'drag' } 
          });

          const source = Marzipano.ImageUrlSource.fromString(objectUrl);
          
          // Геометрия: предполагаем эквиректангулярную (сферическую) панораму
          const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
          
          // Ограничитель обзора
          const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            (120 * Math.PI) / 180
          );
          
          // Начальный вид
          const view = new Marzipano.RectilinearView({ yaw: Math.PI, pitch: 0, roll: 0, fov: Math.PI / 4 }, limiter);

          const scene = currentViewer.createScene({
            source: source,
            geometry: geometry,
            view: view,
          });

          scene.switchTo({ transitionDuration: 0 }); // Убираем анимацию при первой загрузке
          viewerInstanceRef.current = currentViewer;
        }

      } catch (err: any) {
        console.error('Error initializing panorama:', err);
        if (isMounted) setError(err.message || 'Ошибка загрузки панорамы');
      }
    };

    initializeViewer();

    // Очистка
    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      // Marzipano cleanup
      if (viewerInstanceRef.current) {
         // Нет официального метода destroy, просто обнуляем ссылку
         viewerInstanceRef.current = null;
      }
    };
  }, [markerId]);

  return (
    <div className="panorama-container" style={{ width: '100%', height: '100%', position: 'relative', background: '#000' }}>
      
      {/* Сообщение об ошибке */}
      {error && (
        <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: 'red',
            background: 'rgba(0,0,0,0.8)',
            padding: '20px',
            borderRadius: '8px',
            zIndex: 10
        }}>
            {error}
        </div>
      )}

      <div 
        ref={viewerRef} 
        className="panorama-viewer" 
        style={{ width: '100%', height: '100%', cursor: 'grab', outline: 'none' }}
      ></div>

      {/* Интерфейс поверх панорамы */}
      <div style={{ position: 'absolute', bottom: '20px', left: '20px', zIndex: 1000, display: 'flex', gap: '10px' }}>
          <button 
            onClick={toggleFullscreen}
            style={{
              padding: '6px 12px',
              background: 'rgba(255,255,255,0.8)',
              color: '#333',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold'
            }}
          >
            {isFullscreen ? 'Свернуть' : 'На весь экран'}
          </button>
      </div>

      {pointData && (
        <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            color: 'white',
            textShadow: '0 1px 4px rgba(0,0,0,0.8)',
            zIndex: 5,
            pointerEvents: 'none',
            background: 'rgba(0,0,0,0.3)',
            padding: '5px 10px',
            borderRadius: '4px'
        }}>
          <h3 style={{margin: 0, fontSize: '14px'}}>{pointData.filename}</h3>
          <span style={{fontSize: '11px', opacity: 0.8}}>{pointData.upload_date || pointData.timestamp}</span>
        </div>
      )}
    </div>
  );
};

export default PanoramaViewer;