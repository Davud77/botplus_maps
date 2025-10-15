import React, { useRef, useEffect, useState } from 'react';
import Marzipano from 'marzipano';

interface PanoramaViewerProps {
  markerId: string;      // Обратите внимание, что теперь точно string, без null
  isExpanded: boolean;   // если нужно регулировать высоту
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);
  // Если нужно показывать блок с информацией, включаем флажок:
  const [showPointInfo] = useState<boolean>(false);
  const [pointData, setPointData] = useState<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  useEffect(() => {
    let objectUrl: string | null = null;
    let currentViewer: any = null;

    // Функция инициализации Marzipano
    const initializeViewer = async () => {
      try {
        // 1. Загружаем информацию о панораме (атрибуты), если требуется
        const response = await fetch(`https://api.botplus.ru/pano_info/${markerId}`);
        const data = await response.json();
        setPointData(data);

        // 2. Загружаем само изображение как Blob
        const fileResponse = await fetch(`https://api.botplus.ru/pano_info/${markerId}/download`);
        const blob = await fileResponse.blob();

        // 3. Создаём локальный объект-URL из Blob
        objectUrl = URL.createObjectURL(blob);

        // 4. Если наш div для Marzipano существует, создаём Viewer
        if (viewerRef.current) {
          currentViewer = new Marzipano.Viewer(viewerRef.current, {
            stage: { progressive: true },
          });

          // Источник – ссылка на blob (как обычная строка URL)
          const source = Marzipano.ImageUrlSource.fromString(objectUrl);

          // Указываем, что панорама у нас equirect (360x180)
          // Можно выставить точную ширину, если знаете (например, 8000 px)
          const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);

          // Ограничитель обзора, чтоб слишком не "отъезжать"
          const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            (120 * Math.PI) / 180
          );

          // Начальный вид (yaw: Math.PI – это разворот "назад")
          const view = new Marzipano.RectilinearView({ yaw: Math.PI }, limiter);

          // Создаём сцену
          const scene = currentViewer.createScene({
            source: source,
            geometry: geometry,
            view: view,
          });

          // Плавно переключаемся на неё
          scene.switchTo({ transitionDuration: 500 });

          // Сохраняем инстанс, чтобы потом удалить при размонтаже
          viewerInstanceRef.current = currentViewer;
        }
      } catch (error) {
        console.error('Ошибка при инициализации панорамы:', error);
      }
    };

    // Если markerId не пуст, загружаем панораму
    if (markerId) {
      initializeViewer();
    }

    // Очистка при смене или размонтаже
    return () => {
      if (currentViewer) {
        currentViewer.destroy();
      }
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [markerId]);

  return (
    <div className="panorama-container">
      <div
        ref={viewerRef}
        className="panorama-viewer"
      >
        <button 
          onClick={toggleFullscreen}
          style={{
            position: 'absolute',
            bottom: '20px',
            left: '20px',
            zIndex: 1000,
            padding: '8px 16px',
            background: 'var(--color-surface-alt)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-base)',
            cursor: 'pointer',
          }}
        >
          {isFullscreen ? 'Свернуть' : 'На весь экран'}
        </button>
        {/* Если нужно выводить инфу поверх панорамы */}
        {showPointInfo && pointData && (
          <div className="point-info-overlay">
            <h2>{pointData.filename}</h2>
            {/* ...и т.д. */}
          </div>
        )}
      </div>
    </div>
  );
};

export default PanoramaViewer;