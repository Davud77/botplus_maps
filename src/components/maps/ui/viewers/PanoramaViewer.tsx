import React, { useRef, useEffect, useState } from 'react';
// Если у вас нет типов для marzipano, можно добавить:
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

  // Обработчик полноэкранного режима
  const toggleFullscreen = () => {
    if (viewerRef.current) {
      if (!isFullscreen) {
        if (viewerRef.current.requestFullscreen) {
          viewerRef.current.requestFullscreen();
        }
        setIsFullscreen(true);
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        }
        setIsFullscreen(false);
      }
    }
  };

  // Слушатель изменения полноэкранного режима
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Инициализация Marzipano
  useEffect(() => {
    let objectUrl: string | null = null;
    let currentViewer: any = null;

    const initializeViewer = async () => {
      if (!markerId) return;

      try {
        // 1. Получаем метаданные
        const response = await fetch(`https://api.botplus.ru/pano_info/${markerId}`);
        if (response.ok) {
          const data = await response.json();
          setPointData(data);
        }

        // 2. Получаем изображение (blob)
        const fileResponse = await fetch(`https://api.botplus.ru/pano_info/${markerId}/download`);
        const blob = await fileResponse.blob();
        objectUrl = URL.createObjectURL(blob);

        // 3. Инициализируем просмотрщик
        if (viewerRef.current) {
          // Уничтожаем старый инстанс, если был (хотя useEffect cleanup тоже сработает)
          if (viewerInstanceRef.current) {
             // Marzipano не всегда имеет метод destroy, но если есть - вызываем
             // viewerInstanceRef.current.destroy(); 
          }

          currentViewer = new Marzipano.Viewer(viewerRef.current, {
            stage: { progressive: true },
            controls: { mouseViewMode: 'drag' } 
          });

          const source = Marzipano.ImageUrlSource.fromString(objectUrl);
          const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
          
          // Ограничиваем вертикальный обзор, чтобы не видеть черные полюса (если панорама не полная сфера)
          const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            (120 * Math.PI) / 180
          );
          
          const view = new Marzipano.RectilinearView({ yaw: Math.PI }, limiter);

          const scene = currentViewer.createScene({
            source: source,
            geometry: geometry,
            view: view,
          });

          scene.switchTo({ transitionDuration: 500 });
          viewerInstanceRef.current = currentViewer;
        }
      } catch (error) {
        console.error('Error initializing panorama:', error);
      }
    };

    initializeViewer();

    // Очистка
    return () => {
      // Если Marzipano не предоставляет явного метода destroy для viewer, 
      // можно попробовать очистить DOM узел, но обычно достаточно отпустить ссылки.
      // viewerInstanceRef.current = null; 
      
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [markerId]);

  return (
    <div className="panorama-container" style={{ width: '100%', height: '100%', position: 'relative', background: '#000' }}>
      <div 
        ref={viewerRef} 
        className="panorama-viewer" 
        style={{ width: '100%', height: '100%', cursor: 'grab' }}
      >
        {/* Кнопка фулскрин */}
        <button 
          onClick={toggleFullscreen}
          style={{
            position: 'absolute',
            bottom: '20px',
            left: '20px',
            zIndex: 1000,
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

        {/* Название точки */}
        {pointData && (
          <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              color: 'white',
              textShadow: '0 1px 4px rgba(0,0,0,0.8)',
              zIndex: 5,
              pointerEvents: 'none'
          }}>
            <h3 style={{margin: 0, fontSize: '14px'}}>{pointData.filename}</h3>
            <span style={{fontSize: '11px', opacity: 0.8}}>{pointData.upload_date}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default PanoramaViewer;