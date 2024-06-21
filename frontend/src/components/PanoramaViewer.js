import React, { useRef, useEffect } from 'react';
import Marzipano from 'marzipano';

const PanoramaViewer = ({ imageUrl, isExpanded }) => {
  const viewerRef = useRef(null);
  const viewerInstanceRef = useRef(null);

  useEffect(() => {
    if (viewerRef.current && imageUrl) {
      const viewer = new Marzipano.Viewer(viewerRef.current);
      const source = Marzipano.ImageUrlSource.fromString(imageUrl);
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

      return () => {
        const currentViewer = viewerInstanceRef.current;
        if (currentViewer) {
          currentViewer.destroy();
        }
        viewerInstanceRef.current = null;
      };
    }
  }, [imageUrl]);

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

  return (
    <div ref={viewerRef} style={{
      width: '100%',
      height: isExpanded ? '100vh' : '50vh',
      transition: 'height 0.5s ease'
    }} />
  );
};

export default PanoramaViewer;