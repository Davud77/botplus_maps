// src/components/maps/MapPage.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// --- STORES & HOOKS ---
import { useUIStore } from './hooks/useUIStore';
import { useMapStore } from './hooks/useMapStore';

// --- UI COMPONENTS ---
import { MapHeader } from './ui/MapHeader';
import { VectorPanel } from './ui/panels/VectorPanel';
import { OrthoPanel } from './ui/panels/OrthoPanel';
import { BaseLayersPanel } from './ui/panels/BaseLayersPanel';
import { PanoPanel } from './ui/panels/PanoPanel';

// --- VIEWERS ---
import PanoramaViewer from './ui/viewers/PanoramaViewer';

// --- LAYERS ---
import PanoLayer from './layers/PanoLayer';
import { VectorLayerRenderer } from './layers/VectorLayerRenderer';
import { OrthoTileLayer } from './layers/OrthoLayer';

// --- CORE ---
import CustomZoomControl from './core/CustomZoomControl';
import { MapEventHandlers, handleCopyCoordinates, ContextMenu } from './ui/ContextMenu';

interface MarkerType { id: string; lat: number; lng: number; }

const MapPage: React.FC = () => {
  // Global Stores
  const { activePanel, closeAll } = useUIStore();
  const { baseLayerUrl } = useMapStore();

  // Local State (Map & View)
  const [mapCenter, setMapCenter] = useState<[number, number]>([43, 47]);
  
  // Pano State
  const [showPanoLayer, setShowPanoLayer] = useState(false);
  const [isLoadingPano, setIsLoadingPano] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState<string | null>(null);
  const [isPanoExpanded, setIsPanoExpanded] = useState(false);
  const [isPanoVisible, setIsPanoVisible] = useState(false);

  // Context Menu State
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });

  const mapRef = useRef<L.Map | null>(null);

  // Синхронизация: если открыта панель панорам, включаем слой на карте автоматически
  useEffect(() => {
    if (activePanel === 'pano') {
      setShowPanoLayer(true);
    }
  }, [activePanel]);

  // --- Handlers ---

  const handleMarkerClick = useCallback(async (marker: MarkerType) => {
    setSelectedMarker(marker.id);
    setIsPanoVisible(true);
  }, []);

  const handleSearch = (input: string) => {
    const coords = input.split(',').map(c => parseFloat(c.trim()));
    if (coords.length === 2 && !isNaN(coords[0])) {
      mapRef.current?.setView(coords as [number, number], 18);
    }
  };

  const SetMapRef = () => {
    const map = useMap();
    useEffect(() => { mapRef.current = map; }, [map]);
    return null;
  };

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative', overflow: 'hidden' }}>
      
      {/* 1. HEADER */}
      <MapHeader 
        onSearch={handleSearch}
        onTogglePano={() => setShowPanoLayer(!showPanoLayer)}
        isPanoLoading={isLoadingPano}
      />

      {/* 2. SIDE PANELS */}
      {activePanel === 'vector' && <VectorPanel onClose={closeAll} />}
      {activePanel === 'baseLayers' && <BaseLayersPanel onClose={closeAll} />}
      {/* Передаем mapRef.current в OrthoPanel для управления зумом */}
      {activePanel === 'ortho' && <OrthoPanel onClose={closeAll} map={mapRef.current} />}
      {activePanel === 'pano' && <PanoPanel onClose={closeAll} />}

      {/* 3. PANORAMA VIEWER */}
      {selectedMarker && isPanoVisible && (
        <div className="selected-marker-info" style={{ height: isPanoExpanded ? '100%' : '50%' }}>
          <PanoramaViewer markerId={selectedMarker} isExpanded={isPanoExpanded} />
          
          <button 
            onClick={() => setIsPanoVisible(false)}
            style={{
              position:'absolute', top:10, right:10, zIndex:2000, 
              background:'white', border:'none', borderRadius:'50%', 
              width:30, height:30, cursor:'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
            title="Закрыть"
          >
            ✕
          </button>
          
          <button 
            onClick={() => setIsPanoExpanded(!isPanoExpanded)}
            style={{
              position:'absolute', top:10, right:50, zIndex:2000, 
              background:'white', border:'none', borderRadius:'4px', 
              padding:'5px 10px', cursor:'pointer', fontSize: '12px', fontWeight: 'bold'
            }}
          >
            {isPanoExpanded ? 'Свернуть' : 'Развернуть'}
          </button>
        </div>
      )}

      {/* 4. MAP CONTAINER */}
      <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false} maxZoom={20}>
        <SetMapRef />
        <TileLayer url={baseLayerUrl} maxZoom={20} />
        <CustomZoomControl />

        {/* --- Layers --- */}
        <VectorLayerRenderer />
        <OrthoTileLayer />

        {showPanoLayer && (
          <PanoLayer selectedMarker={selectedMarker} onMarkerClick={handleMarkerClick} />
        )}

        {/* --- Events --- */}
        <MapEventHandlers setContextMenu={setContextMenu} />
      </MapContainer>

      {/* 5. CONTEXT MENU */}
      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={() => handleCopyCoordinates(contextMenu)} />
    </div>
  );
};

export default MapPage;