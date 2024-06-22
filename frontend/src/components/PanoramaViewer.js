import React, { useRef, useEffect, useState } from 'react';
import Marzipano from 'marzipano';
import PointInfo from './PointInfo';
import '../assets/css/styles.css';

const PanoramaViewer = ({ markerId, isExpanded }) => {
  const viewerRef = useRef(null);
  const viewerInstanceRef = useRef(null);
  const [showPointInfo, setShowPointInfo] = useState(false);
  const [pointData, setPointData] = useState(null);

  useEffect(() => {
    if (markerId) {
      fetch(`https://api.botplus.ru/panorama_info?id=${markerId}`)
        .then(response => response.json())
        .then(data => {
          setPointData(data);
          if (viewerRef.current && data.filename) {
            const viewer = new Marzipano.Viewer(viewerRef.current);
            const source = Marzipano.ImageUrlSource.fromString(data.filename);
            const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
            const limiter = Marzipano.RectilinearView.limit.traditional(4096, 120 * Math.PI / 180);
            const view = new Marzipano.RectilinearView({ yaw: Math.PI }, limiter);
            const scene = viewer.createScene({
              source: source,
              geometry: geometry,
              view: view
            });

            scene.switchTo();
            viewerInstanceRef.current = viewer;
          }
        })
        .catch(error => console.error('Error fetching point info:', error));
    }

    return () => {
      const currentViewer = viewerInstanceRef.current;
      if (currentViewer) {
        currentViewer.destroy();
      }
      viewerInstanceRef.current = null;
    };
  }, [markerId]);

  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      if (viewerInstanceRef.current && viewerRef.current) {
        try {
          viewerInstanceRef.current.updateSize();
        } catch (error) {
          console.error("Error updating Marzipano viewer size:", error);
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
    <div ref={viewerRef} style={{
      width: '100%',
      height: isExpanded ? '100vh' : '50vh',
      transition: 'height 0.5s ease'
    }}>
      <button className="pointinfo" onClick={handlePointInfoClick}>
        <svg xmlns="http://www.w3.org/2000/svg" height="30px" viewBox="0 0 24 24" width="30px" fill="#ffffff">
          <path d="M0 0h24v24H0V0z" fill="none"/>
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
        </svg>
      </button>
      {showPointInfo && <PointInfo data={pointData} />}
    </div>
  );
};

export default PanoramaViewer;
