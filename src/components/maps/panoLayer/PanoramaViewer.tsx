// src/components/maps/panoLayer/PanoramaViewer.tsx
import React, { useRef, useEffect, useState } from 'react';
import Marzipano from 'marzipano';

interface PanoramaViewerProps {
  markerId: string;      // ID точки (строка)
  isExpanded: boolean;   // если нужно регулировать высоту
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);

  const [showPointInfo] = useState<boolean>(false);
  const [pointData, setPointData] = useState<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = () => {
    if (!viewerRef.current) return;
    if (!isFullscreen) {
      viewerRef.current.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  useEffect(() => {
    let objectUrl: string | null = null;
    let currentViewer: any = null;

    const initializeViewer = async () => {
      try {
        // 1) Метаданные точки
        const metaRes = await fetch(`/api/pano_info/${encodeURIComponent(markerId)}`, {
          method: 'GET',
          credentials: 'include',
          headers: { Accept: 'application/json' },
        });
        if (!metaRes.ok) {
          const txt = await metaRes.text().catch(() => '');
          throw new Error(`Meta HTTP ${metaRes.status} ${metaRes.statusText} ${txt}`);
        }
        const meta = await metaRes.json();
        setPointData(meta);

        // 2) Файл панорамы (Blob)
        const fileRes = await fetch(`/api/pano_info/${encodeURIComponent(markerId)}/download`, {
          method: 'GET',
          credentials: 'include',
        });
        if (!fileRes.ok) {
          const txt = await fileRes.text().catch(() => '');
          throw new Error(`File HTTP ${fileRes.status} ${fileRes.statusText} ${txt}`);
        }
        const blob = await fileRes.blob();

        // 3) Локальный объект-URL
        objectUrl = URL.createObjectURL(blob);

        // 4) Инициализация Marzipano
        if (viewerRef.current) {
          currentViewer = new Marzipano.Viewer(viewerRef.current, {
            stage: { progressive: true },
          });

          // Источник — локальный blob-url
          const source = Marzipano.ImageUrlSource.fromString(objectUrl);

          // Геометрия equirect; ширину можно увеличить, если известно реальное разрешение
          const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);

          // Ограничитель обзора
          const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            (120 * Math.PI) / 180
          );

          // Начальный вид
          const view = new Marzipano.RectilinearView({ yaw: Math.PI }, limiter);

          // Сцена
          const scene = currentViewer.createScene({
            source,
            geometry,
            view,
          });

          scene.switchTo({ transitionDuration: 500 });
          viewerInstanceRef.current = currentViewer;
        }
      } catch (err) {
        console.error('Ошибка при инициализации панорамы:', err);
      }
    };

    if (markerId) {
      initializeViewer();
    }

    // Очистка
    return () => {
      if (currentViewer) {
        try {
          currentViewer.destroy();
        } catch {
          /* ignore */
        }
      }
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [markerId]);

  return (
    <div className="panorama-container" style={{ height: isExpanded ? '70vh' : '40vh' }}>
      <div ref={viewerRef} className="panorama-viewer" style={{ position: 'relative', height: '100%' }}>
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

        {showPointInfo && pointData && (
          <div className="point-info-overlay">
            <h2>{pointData?.filename}</h2>
            {/* дополнительные поля при необходимости */}
          </div>
        )}
      </div>
    </div>
  );
};

export default PanoramaViewer;
