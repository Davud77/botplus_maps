// Файл: src/PanoramaViewer.js
import React, { useRef, useEffect } from 'react';
import Marzipano from 'marzipano';

const PanoramaViewer = ({ imageUrl }) => {
  const viewerRef = useRef(null);

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
      return () => viewer.destroy();
    }
  }, [imageUrl]);

  return <div ref={viewerRef} style={{ width: '100%', height: '500px' }} />;
};

export default PanoramaViewer;
