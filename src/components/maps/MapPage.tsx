import { LayerPane } from './layers/LayerPane';
// src/components/maps/MapPage.tsx
import { useVectorStore } from './hooks/useVectorStore';
import { useLayerStyleStore } from './hooks/useLayerStyleStore';
import { ActiveLayersPanel } from './ui/panels/ActiveLayersPanel';
import { CoordinateReadout } from './ui/CoordinateReadout';
import { MapConfig } from '../../utils/workspaceApi';
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// --- STYLES ---
// Map layout styles are currently part of the global index.css bundle.

// --- STORES & HOOKS ---
import { useUIStore } from './hooks/useUIStore';
import { useMapStore } from './hooks/useMapStore';

// --- UI COMPONENTS ---
import { BasePanel } from './ui/panels/BasePanel';
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

function MapStateObserver({ mapRef, onViewChange, onZoomChange }: {
  mapRef: React.MutableRefObject<L.Map | null>;
  onViewChange?: (view: MapConfig['view']) => void; onZoomChange: (zoom: number) => void;
}) {
  const map = useMap();
  useEffect(() => {
    mapRef.current = map;
    useMapStore.getState().setMapInstance(map);
    onZoomChange(map.getZoom());
    const zoom = () => onZoomChange(map.getZoom());
    const move = () => {
      const center = map.getCenter().wrap();
      onViewChange?.({ center: [Math.max(-85.051129, Math.min(85.051129, center.lat)), center.lng], zoom: map.getZoom() });
    };
    map.on('moveend', move); map.on('zoomend', zoom);
    return () => {
      map.off('moveend', move); map.off('zoomend', zoom);
      if (mapRef.current === map) mapRef.current = null;
      if (useMapStore.getState().mapInstance === map) useMapStore.setState({ mapInstance: null });
    };
  }, [map, mapRef, onViewChange, onZoomChange]);
  return null;
}

interface MapPageProps { initialConfig?: MapConfig; readOnly?: boolean; documentControls?: React.ReactNode;
  onViewChange?: (view: MapConfig['view']) => void; onPanoramasChange?: (enabled: boolean) => void; }
const MapPage: React.FC<MapPageProps> = ({ initialConfig, readOnly = false, documentControls, onViewChange, onPanoramasChange }) => {
  // Global Stores
  const { activePanel, closeAll } = useUIStore();
  const { baseLayerUrl, baseDefinition } = useMapStore();
  const selectedOrthoIds=useMapStore(s=>s.selectedOrthoIds);
  const activeVectorIds=useVectorStore(s=>s.activeVectorIds);
  const presentations=useLayerStyleStore(s=>s.layers);

  // Local State (Map & View)
  const mapCenter: [number, number] = initialConfig?.view.center || [43, 47];

  // Для отладки: храним текущий зум
  const [currentZoom, setCurrentZoom] = useState<number>(5);

  // Pano State
  const [showPanoLayer, setShowPanoLayer] = useState(initialConfig?.show_panoramas || false);
  const isLoadingPano = false;
  const [selectedMarker, setSelectedMarker] = useState<string | null>(null);
  const [isPanoVisible, setIsPanoVisible] = useState(false);

  // Состояние для метаданных панорамы
  const [panoDetails, setPanoDetails] = useState<{ title: string; date: string; alt: string } | null>(null);

  // Context Menu State
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });

  const mapRef = useRef<L.Map | null>(null);
  // Ref для контейнера панорамы, чтобы управлять Fullscreen
  const panoContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    useLayerStyleStore.getState().sync([...[...activeVectorIds].map(id=>`vector:${id}`),...selectedOrthoIds.map(id=>`ortho:${id}`),...(showPanoLayer?['panoramas']:[]),...(baseLayerUrl?['basemap']:[])]);
  }, [selectedOrthoIds,activeVectorIds,showPanoLayer,baseLayerUrl]);

  useEffect(() => { onPanoramasChange?.(showPanoLayer); }, [showPanoLayer, onPanoramasChange]);

  // --- ВАЖНО: Фикс размера карты, управление классами и скрытие .end-box ---
  useEffect(() => {
    // 1. Управление классами контейнера карты
    if (mapRef.current) {
      const mapContainerHtmlElement = mapRef.current.getContainer();

      if (isPanoVisible) {
        mapContainerHtmlElement.classList.add('minimap-mode', 'main-map-container-pano');
      } else {
        mapContainerHtmlElement.classList.remove('minimap-mode', 'main-map-container-pano');
      }

      setTimeout(() => {
        mapRef.current?.invalidateSize(true);
      }, 300);
    }

  }, [isPanoVisible]);

  // --- Handlers ---

  const toggleFullscreen = () => {
    if (panoContainerRef.current) {
      if (!document.fullscreenElement) {
        panoContainerRef.current.requestFullscreen().catch((err) => {
          console.error(`Error attempting to enable full-screen mode: ${err.message}`);
        });
      } else {
        document.exitFullscreen();
      }
    }
  };

  const handleMarkerClick = useCallback(async (marker: MarkerType) => {
    if (mapRef.current) {
      mapRef.current.panTo([marker.lat, marker.lng]);
    }
    setSelectedMarker(marker.id);
    setIsPanoVisible(true);
  }, []);

  const handleSearch = (input: string) => {
    const coords = input.split(',').map(c => parseFloat(c.trim()));
    if (coords.length === 2 && !isNaN(coords[0])) {
      mapRef.current?.setView(coords as [number, number], 18);
    }
  };

  return (
    <div className="map-page-wrapper">

      {/* 1. HEADER */}
      <div className="ui-overlay-layer">
        <MapHeader
          showSettings={!!documentControls}
          readOnly={readOnly}
          onSearch={handleSearch}
          onTogglePano={() => {setShowPanoLayer(true);useLayerStyleStore.getState().update('panoramas',{visible:true});}}
          isPanoLoading={isLoadingPano}
        />
      </div>

      {/* 2. SIDE PANELS */}
      <div className="ui-overlay-layer">
        {activePanel === 'settings' && documentControls && <BasePanel title="Настройки карты" onClose={closeAll}>{documentControls}</BasePanel>}
      </div>
      <div className="ui-overlay-layer" hidden={readOnly}>
        {activePanel === 'activeLayers' && <ActiveLayersPanel onClose={closeAll} onRemovePanos={()=>setShowPanoLayer(false)} />}
        {activePanel === 'vector' && <VectorPanel onClose={closeAll} />}
        {activePanel === 'baseLayers' && <BaseLayersPanel onClose={closeAll} />}
        {activePanel === 'ortho' && <OrthoPanel onClose={closeAll} map={mapRef.current} />}

        {activePanel === 'pano' && (
          <PanoPanel
            onClose={closeAll}
            panoDetails={isPanoVisible ? panoDetails : null} added={showPanoLayer} onAdd={()=>{setShowPanoLayer(true);useLayerStyleStore.getState().update('panoramas',{visible:true});}}
          />
        )}
      </div>

      {/* 3. PANORAMA VIEWER */}
      {selectedMarker && isPanoVisible && (
        <div ref={panoContainerRef} className="panorama-viewer-container">
          <PanoramaViewer
            markerId={selectedMarker}
            isExpanded={true}
            onDataLoad={(data) => setPanoDetails(data)}
          />

          <div className="pano-controls-overlay">
            {/* Кнопка Fullscreen с картинкой */}
            <button
              onClick={toggleFullscreen}
              className="layers-button pano-fullscreen-btn"
              title="На весь экран"
              aria-label="На весь экран"
            >
              <span aria-hidden="true">⛶</span>
            </button>

            {/* Кнопка Закрыть с картинкой */}
            <button
              onClick={() => {
                setIsPanoVisible(false);
                setPanoDetails(null);
              }}
              className="layers-button pano-close-btn"
              title="Закрыть"
            >
              <img src="/images/svg/close-icon.svg" alt="Закрыть" width="24" height="24" />
            </button>
          </div>
        </div>
      )}

      {/* 4. MAP CONTAINER */}
      <MapContainer
        center={mapCenter}
        zoom={initialConfig?.view.zoom ?? 5}
        className="main-map-container"
        zoomControl={false}
        maxZoom={23}
        preferCanvas={true} // Use Canvas instead of one SVG node per point.
      >
        <MapStateObserver mapRef={mapRef} onViewChange={onViewChange} onZoomChange={setCurrentZoom} />
        {baseLayerUrl && presentations.find(item=>item.key==='basemap')?.visible!==false && <LayerPane name="basemap-overlay" style={{zIndex:400+presentations.length-Math.max(0,presentations.findIndex(item=>item.key==='basemap')),opacity:presentations.find(item=>item.key==='basemap')?.opacity??1}}><TileLayer key={baseLayerUrl} url={baseLayerUrl} maxZoom={24} maxNativeZoom={baseDefinition?.max_zoom??22} tms={baseDefinition?.scheme==='tms'} attribution={baseDefinition?.attribution||''} /></LayerPane>}
        <CustomZoomControl />
        <CoordinateReadout />

        {/* --- Layers --- */}
        <VectorLayerRenderer />
        <OrthoTileLayer />

        {showPanoLayer && presentations.find(item=>item.key==='panoramas')?.visible!==false && (
          <LayerPane name="panoramas-overlay" style={{zIndex:400+presentations.length-Math.max(0,presentations.findIndex(item=>item.key==='panoramas')),opacity:presentations.find(item=>item.key==='panoramas')?.opacity??1}}><PanoLayer pane="panoramas-overlay" selectedMarker={selectedMarker} onMarkerClick={handleMarkerClick} /></LayerPane>
        )}

        {/* --- Events --- */}
        <MapEventHandlers setContextMenu={setContextMenu} />
      </MapContainer>

      {!baseLayerUrl && !readOnly && <div className="map-no-basemap-hint">Подложка отключена · ваши слои отображаются локально. Выбрать фон: «Слои карты».</div>}
      {/* 5. CONTEXT MENU */}
      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={() => handleCopyCoordinates(contextMenu)} />

      {/* --- БЛОК ОТЛАДКИ ЗУМА --- */}
      <div className="debug-zoom-panel">
        Zoom: {currentZoom}
      </div>

    </div>
  );
};

export default MapPage;
