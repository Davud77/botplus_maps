// src/components/maps/ui/viewers/PanoramaViewer.tsx

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

  // --- Fullscreen Handlers ---
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

  // --- Viewer Initialization ---
  useEffect(() => {
    let objectUrl: string | null = null;
    let isMounted = true; 

    const initializeViewer = async () => {
      if (!markerId) return;
      setError(null);
      setPointData(null);

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
        if (isMounted) setPointData(data);

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
    <div className="panorama-container" style={{ width: '100%', height: '100%', position: 'relative', background: '#222', overflow: 'hidden' }}>
      
      {/* Error Overlay */}
      {error && (
        <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#ff6b6b',
            background: 'rgba(0,0,0,0.8)',
            padding: '20px',
            borderRadius: '8px',
            zIndex: 20,
            textAlign: 'center',
            maxWidth: '80%'
        }}>
            <div style={{fontSize: '24px', marginBottom: '10px'}}>⚠️</div>
            {error}
        </div>
      )}

      {/* Viewer Container */}
      <div 
        ref={viewerRef} 
        className="panorama-viewer" 
        style={{ width: '100%', height: '100%', cursor: 'grab', outline: 'none' }}
      ></div>

      {/* Controls Overlay */}
      <div style={{ position: 'absolute', bottom: '20px', left: '20px', zIndex: 10, display: 'flex', gap: '10px' }}>
          <button 
            onClick={toggleFullscreen}
            style={{
              padding: '8px 16px',
              background: 'rgba(30,30,30,0.8)',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: '500',
              backdropFilter: 'blur(4px)'
            }}
          >
            {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          </button>
      </div>

      {/* Info Overlay */}
      {pointData && (
        <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            color: 'white',
            textShadow: '0 1px 2px rgba(0,0,0,0.8)',
            zIndex: 10,
            pointerEvents: 'none',
            background: 'linear-gradient(to right, rgba(0,0,0,0.6), transparent)',
            padding: '8px 12px',
            borderRadius: '4px'
        }}>
          <h3 style={{margin: 0, fontSize: '14px', fontWeight: '600'}}>{pointData.filename}</h3>
          <div style={{fontSize: '11px', opacity: 0.8, marginTop: '2px'}}>
             {pointData.timestamp || pointData.upload_date || 'No date'}
          </div>
          {pointData.altitude !== 0 && (
              <div style={{fontSize: '11px', opacity: 0.8}}>
                  Alt: {pointData.altitude?.toFixed(1)}m
              </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PanoramaViewer;