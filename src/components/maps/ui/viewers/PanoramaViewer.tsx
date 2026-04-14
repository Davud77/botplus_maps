// src/components/maps/ui/viewers/PanoramaViewer.tsx

import React, { useRef, useEffect, useState } from 'react';
// @ts-ignore
import Marzipano from 'marzipano';

interface PanoramaViewerProps {
  markerId: string;
  isExpanded: boolean;
  onDataLoad?: (data: { title: string; date: string; alt: string }) => void;
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded, onDataLoad }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);

  // --- Viewer Initialization ---
  useEffect(() => {
    let objectUrl: string | null = null;
    let isMounted = true; 

    const initializeViewer = async () => {
      if (!markerId) return;
      setError(null);

      // Cleanup previous viewer instance immediately
      if (viewerInstanceRef.current) {
         viewerInstanceRef.current = null;
         if (viewerRef.current) viewerRef.current.innerHTML = '';
      }

      try {
        // [FIX] Correct API path with /api prefix
        const infoUrl = `/api/pano_info/${markerId}`;
        const infoResponse = await fetch(infoUrl);
        
        const contentType = infoResponse.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) {
             throw new Error("API returned HTML instead of JSON. Check backend routing.");
        }

        if (!infoResponse.ok) {
           throw new Error(`Failed to load info: ${infoResponse.status}`);
        }
        
        const data = await infoResponse.json();
        
        if (isMounted) {
          // Отправляем данные наверх в MapPage
          if (onDataLoad) {
            onDataLoad({
              title: data.filename || `Panorama ${markerId}`,
              date: data.timestamp || data.upload_date || 'No date',
              alt: data.altitude ? data.altitude.toFixed(1) : '0'
            });
          }
        }

        // [FIX] Correct API path for download
        const imageUrl = `/api/pano_info/${markerId}/download`;
        const imageResponse = await fetch(imageUrl);
        
        if (!imageResponse.ok) {
            throw new Error(`Failed to load image: ${imageResponse.status}`);
        }

        const blob = await imageResponse.blob();
        if (!isMounted) return;

        objectUrl = URL.createObjectURL(blob);

        if (viewerRef.current) {
          // Double check cleanup
          viewerRef.current.innerHTML = '';

          // Create Viewer
          const viewer = new Marzipano.Viewer(viewerRef.current, {
            stage: { progressive: true },
            controls: { mouseViewMode: 'drag' } 
          });

          const source = Marzipano.ImageUrlSource.fromString(objectUrl);
          
          // Geometry (Equirectangular)
          const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
          
          // View Limiter
          const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            (120 * Math.PI) / 180
          );
          
          // Initial View
          // Use direction from data if available, otherwise 0
          const initialYaw = data.direction ? (data.direction * Math.PI / 180) : 0;
          
          const view = new Marzipano.RectilinearView({ 
              yaw: initialYaw, 
              pitch: 0, 
              roll: 0, 
              fov: Math.PI / 4 
          }, limiter);

          const scene = viewer.createScene({
            source: source,
            geometry: geometry,
            view: view,
          });

          scene.switchTo({ transitionDuration: 0 }); 
          viewerInstanceRef.current = viewer;
        }

      } catch (err: any) {
        console.error('Error initializing panorama:', err);
        if (isMounted) setError(err.message || 'Error loading panorama');
      }
    };

    initializeViewer();

    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      if (viewerInstanceRef.current) {
         viewerInstanceRef.current = null;
      }
    };
  }, [markerId]);

  return (
    <div className="panorama-container">
      
      {/* Error Overlay */}
      {error && (
        <div className="pano-error-overlay">
            <div className="pano-error-icon">⚠️</div>
            {error}
        </div>
      )}

      {/* Viewer Container */}
      <div 
        ref={viewerRef} 
        className="panorama-viewer" 
      ></div>
      
    </div>
  );
};

export default PanoramaViewer;