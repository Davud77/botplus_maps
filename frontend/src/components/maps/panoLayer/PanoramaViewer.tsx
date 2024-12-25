// src/components/maps/panoLayer/PanoramaViewer.tsx
import React, { useRef, useEffect, useState } from 'react';
import Marzipano from 'marzipano';
import PointInfo from './PointInfo';
import '../../../assets/css/styles.css';

interface PanoramaViewerProps {
  markerId: string;
  isExpanded: boolean;
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);
  const [showPointInfo, setShowPointInfo] = useState<boolean>(false);
  const [pointData, setPointData] = useState<any>(null);

  useEffect(() => {
    let objectUrl: string | null = null; // Чтобы потом освобождать Blob

    if (markerId) {
      // 1) Получаем общую информацию о панораме
      fetch(`http://localhost:5080/pano_info/${markerId}`)
        .then((response) => response.json())
        .then((data) => {
          setPointData(data);
          // 2) Затем делаем запрос на файл (download)
          //    /pano_info/<markerId>/download
          return fetch(`http://localhost:5080/pano_info/${markerId}/download`);
        })
        .then((fileResponse) => {
          // Превращаем ответ в Blob (бинарный файл)
          return fileResponse.blob();
        })
        .then((blob) => {
          // 3) Создаём локальную blob-ссылку
          objectUrl = URL.createObjectURL(blob);

          // 4) Инициализируем Marzipano
          if (viewerRef.current) {
            const viewer = new Marzipano.Viewer(viewerRef.current);
            const source = Marzipano.ImageUrlSource.fromString(objectUrl);
            const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
            const limiter = Marzipano.RectilinearView.limit.traditional(
              4096,
              (120 * Math.PI) / 180
            );
            const view = new Marzipano.RectilinearView({ yaw: Math.PI }, limiter);
            const scene = viewer.createScene({
              source: source,
              geometry: geometry,
              view: view,
            });
            scene.switchTo();
            viewerInstanceRef.current = viewer;
          }
        })
        .catch((error) => console.error('Error fetching panorama info or file:', error));
    }

    return () => {
      // Очистка: уничтожить Marzipano Viewer, освободить Blob
      const currentViewer = viewerInstanceRef.current;
      if (currentViewer) {
        currentViewer.destroy();
      }
      viewerInstanceRef.current = null;

      // Если был создан objectUrl — освободим
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    };
  }, [markerId]);

  // Слежение за ресайзом
  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      if (viewerInstanceRef.current && viewerRef.current) {
        try {
          viewerInstanceRef.current.updateSize();
        } catch (error) {
          console.error('Error updating Marzipano viewer size:', error);
        }
      }
    });

    const currentViewerRef = viewerRef.current;
    if (currentViewerRef) {
      resizeObserver.observe(currentViewerRef);
    }

    return () => {
      if (currentViewerRef) {
        resizeObserver.unobserve(currentViewerRef);
      }
    };
  }, []);

  const handlePointInfoClick = () => {
    setShowPointInfo(!showPointInfo);
  };

  return (
    <div
      ref={viewerRef}
      style={{
        width: '100%',
        height: isExpanded ? '100vh' : '50vh',
        transition: 'height 0.5s ease',
      }}
    >
      <button className="pointinfo" onClick={handlePointInfoClick}>
        {/* Ваш SVG-код или иконка */}
      </button>
      {showPointInfo && <PointInfo data={pointData} />}
    </div>
  );
};

export default PanoramaViewer;
