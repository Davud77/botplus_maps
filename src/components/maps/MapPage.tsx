// src/components/maps/MapPage.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
  GeoJSON,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { Map as LeafletMap } from 'leaflet';

import PanoramaViewer from './panoLayer/PanoramaViewer';
import Search from './Search';
import BaseLayer from './baseLayer/BaseLayer';
import {
  ContextMenu,
  MapEventHandlers,
  handleCopyCoordinates,
} from './ContextMenu';
import { defaultIcon } from '../icons';
import PanoLayer from './panoLayer/PanoLayer';
import PanoLayerButton from './panoLayer/PanoLayerButton';
import OrthoLayer, { OrthoImageType } from './orthoLayer/OrthoLayer';
import OrthoPanel from './orthoLayer/OrthoPanel';
import SelectionPanel from './panoLayer/SelectionPanel';
import CustomZoomControl from './CustomZoomControl';
import ProfileNav from '../ProfileNav';

// Import API
import { 
  fetchVectorDbs, 
  fetchVectorLayers, 
  fetchLayerData,
  VectorLayerItem // Assumes this type is exported from api.ts
} from '../../utils/api'; 

// --- Types ---
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

// Structure for grouping in the menu
interface VectorGroup {
  dbName: string;
  layers: VectorLayerItem[];
}

// Structure to store loaded GeoJSON data
interface LoadedVectorData {
  id: string; // "dbName-schema-tableName"
  data: any;
  type: string;
  name: string;
}

const MapPage: React.FC = () => {
  // --- UI States ---
  const [selectedMarker, setSelectedMarker] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, lat: 0, lng: 0 });
  
  // --- Layers States ---
  const [baseLayer, setBaseLayer] = useState<string>('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png');
  const [showPanoLayer, setShowPanoLayer] = useState<boolean>(false);
  const [isLoadingMarkers, setIsLoadingMarkers] = useState<boolean>(false);
  
  // --- Ortho States ---
  const [orthoImages, setOrthoImages] = useState<OrthoImageType[]>([]);
  const [showOrthoPanel, setShowOrthoPanel] = useState<boolean>(false);
  const [showOrthoLayer, setShowOrthoLayer] = useState<boolean>(false);
  const [selectedOrthos, setSelectedOrthos] = useState<OrthoImageType[]>([]);

  // --- Vector States (NEW) ---
  const [showVectorPanel, setShowVectorPanel] = useState<boolean>(false); // Show layer selection panel
  const [vectorGroups, setVectorGroups] = useState<VectorGroup[]>([]); // List of available layers (metadata)
  const [loadedVectors, setLoadedVectors] = useState<Map<string, LoadedVectorData>>(new Map()); // Cache of loaded data
  const [activeVectorIds, setActiveVectorIds] = useState<Set<string>>(new Set()); // IDs of active layers
  const [loadingLayerId, setLoadingLayerId] = useState<string | null>(null); // Spinner for specific layer

  const [showAddPanoramaButton, setShowAddPanoramaButton] = useState<boolean>(false);
  const [showSelectionPanel, setShowSelectionPanel] = useState(false);
  
  const mapRef = useRef<LeafletMap | null>(null);

  // --- Panorama Handlers ---
  const handleMarkerClick = useCallback(async (marker: MarkerType) => {
    try {
      await fetch(`https://api.botplus.ru/pano_info/${marker.id}`);
      setSelectedMarker(marker.id);
      setIsVisible(true);
    } catch (error) {
      console.error('Error fetching pano info:', error);
    }
  }, []);

  const toggleHeight = useCallback(() => setIsExpanded((prev) => !prev), []);
  const closeInfo = useCallback(() => { setIsVisible(false); setSelectedMarker(null); }, []);
  const copyCoordinatesHandler = useCallback(() => handleCopyCoordinates(contextMenu), [contextMenu]);

  const SetMapRef = () => {
    const map = useMap();
    useEffect(() => { mapRef.current = map; }, [map]);
    return null;
  };

  const handleSearch = (searchInput: string) => {
    const coords = searchInput.split(',').map((c) => parseFloat(c.trim()));
    if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
      if (mapRef.current) mapRef.current.setView(coords as [number, number], 18);
    } else {
      alert('Invalid coordinate format');
    }
  };

  const handleLayerChange = (url: string) => setBaseLayer(url);
  const handlePanoLayerToggle = () => setShowPanoLayer(prev => !prev);

  // --- Ortho Handlers ---
  const handleToggleOrthoLayer = (images: OrthoImageType[]) => {
    setOrthoImages(images);
    setShowOrthoPanel((prev) => !prev);
    setShowOrthoLayer((prev) => !prev);
  };

  const handleOrthoSelect = (ortho: OrthoImageType) => {
    setSelectedOrthos((prev) => {
      if (prev.some((o) => o.id === ortho.id)) return prev.filter((o) => o.id !== ortho.id);
      return [...prev, ortho];
    });
  };

  const fitToOrthoBounds = (ortho: OrthoImageType) => {
    if (!mapRef.current || !ortho.bounds) return;
    const sw = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.west, ortho.bounds.south));
    const ne = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.east, ortho.bounds.north));
    mapRef.current.fitBounds(L.latLngBounds(sw, ne));
  };

  // --- VECTOR LOGIC ---

  // 1. Open panel and load layer structure (metadata)
  const handleToggleVectorPanel = async () => {
    if (showVectorPanel) {
      setShowVectorPanel(false);
      return;
    }

    setShowVectorPanel(true);
    
    // If list is already loaded, don't load again
    if (vectorGroups.length > 0) return;

    try {
      const dbs = await fetchVectorDbs();
      
      // Sort DBs alphabetically
      dbs.sort((a, b) => a.name.localeCompare(b.name));

      const groups: VectorGroup[] = [];

      for (const db of dbs) {
        try {
          const layers = await fetchVectorLayers(db.name);
          // Sorting of layers is handled during rendering (grouping by schema)
          
          if (layers.length > 0) {
            groups.push({ dbName: db.name, layers });
          }
        } catch (e) {
          console.warn(`Failed to load layers for ${db.name}`);
        }
      }
      setVectorGroups(groups);
    } catch (error) {
      console.error("Failed to load vector databases", error);
      alert("Error loading vector database list");
    }
  };

  // 2. Toggle specific layer visibility (Eye icon)
  const toggleVectorLayerVisibility = async (dbName: string, layer: VectorLayerItem) => {
    const layerId = `${dbName}-${layer.schema}-${layer.tableName}`;

    // If layer is already active -> deactivate
    if (activeVectorIds.has(layerId)) {
      const newSet = new Set(activeVectorIds);
      newSet.delete(layerId);
      setActiveVectorIds(newSet);
      return;
    }

    // If layer is inactive -> activate
    // First check if data is in cache
    if (loadedVectors.has(layerId)) {
      const newSet = new Set(activeVectorIds);
      newSet.add(layerId);
      setActiveVectorIds(newSet);
    } else {
      // No data, need to load
      setLoadingLayerId(layerId);
      try {
        const geoJSON = await fetchLayerData(dbName, layer.tableName, layer.schema);
        
        if (geoJSON && geoJSON.features && geoJSON.features.length > 0) {
          const newData: LoadedVectorData = {
            id: layerId,
            data: geoJSON,
            type: layer.geometryType,
            name: `${layer.schema}.${layer.tableName}`
          };
          
          // Save to cache
          setLoadedVectors(prev => new Map(prev).set(layerId, newData));
          
          // Activate visibility
          const newSet = new Set(activeVectorIds);
          newSet.add(layerId);
          setActiveVectorIds(newSet);
        } else {
          alert(`Layer ${layer.tableName} is empty`);
        }
      } catch (error) {
        console.error(`Error loading layer ${layer.tableName}:`, error);
        alert(`Error loading layer ${layer.tableName}`);
      } finally {
        setLoadingLayerId(null);
      }
    }
  };

  // Vector Style
  const getVectorStyle = () => ({
    color: "#ff7800",
    weight: 2,
    opacity: 0.8,
    fillColor: "#ff7800",
    fillOpacity: 0.2
  });

  const MapClickHandler = () => {
    useMapEvents({ click: () => {} });
    return null;
  };

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative' }}>
      <header className="map-header">
        <div className="first-box">
          <div className="logo">
            <a href="/"><img src="/images/logowhite2.png" alt="Logo" className="logo-image"/></a>
          </div>
          <div className="search-bar"><Search handleSearch={handleSearch} /></div>
        </div>
        <div className="end-box">
          {selectedMarker && isVisible ? (
            <div className="map-buttons">
               <button className="button_control pointinfo" onClick={() => console.log('Info')}>
                  <img src="/images/svg/info-icon.svg" alt="Info" width="30" height="30"/>
               </button>
               <div className="visible_control">
                  <button className="button_control" onClick={closeInfo}>
                    <img src="/images/svg/close-icon.svg" alt="Close" width="30" height="30"/>
                  </button>
               </div>
            </div>
          ) : (
            <div className="map-buttons">
              <BaseLayer handleLayerChange={handleLayerChange} />
              <PanoLayerButton handlePanoLayerToggle={handlePanoLayerToggle} isLoading={isLoadingMarkers} />
              
              <button 
                className={`layers-button ${showOrthoLayer ? 'active' : ''}`} 
                onClick={() => handleToggleOrthoLayer(orthoImages)}
                title="Orthophotos"
              >
                <img src="/images/svg/ortho-icon.svg" alt="Ortho" width="24" height="24" className="ortho-icon"/>
              </button>

              {/* VECTOR LAYERS BUTTON */}
              <button
                className={`layers-button ${showVectorPanel ? 'active' : ''}`}
                onClick={handleToggleVectorPanel}
                title="Vector Layers (PostGIS)"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ stroke: 'white', strokeWidth: 2 }}>
                  <path d="M3 6L12 2L21 6V18L12 22L3 18V6Z" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="12" cy="12" r="2" fill="white" stroke="none"/>
                </svg>
              </button>
            </div>
          )}
          <div className="map-buttons"><ProfileNav /></div>
        </div>
      </header>

      {selectedMarker && isVisible && (
        <div className="selected-marker-info" style={{ height: isExpanded ? '100%' : '50%' }}>
          <PanoramaViewer markerId={selectedMarker} isExpanded={isExpanded} />
        </div>
      )}

      {/* --- VECTOR LAYERS PANEL --- */}
      {showVectorPanel && (
        <div className="ortho-panel" style={{ 
            position: 'absolute', 
            top: '80px', 
            right: '20px', 
            zIndex: 1000,
            background: 'white',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
            width: '320px',
            maxHeight: '70vh',
            display: 'flex',
            flexDirection: 'column'
        }}>
          <div style={{ padding: '15px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#333' }}>Vector Layers</h3>
            <button onClick={() => setShowVectorPanel(false)} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: '20px' }}>&times;</button>
          </div>
          
          <div style={{ overflowY: 'auto', padding: '10px' }}>
            {vectorGroups.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#999' }}>Loading layers...</div>
            ) : (
              vectorGroups.map((group) => {
                // Group layers by Schema
                const layersBySchema: { [key: string]: VectorLayerItem[] } = {};
                group.layers.forEach(layer => {
                  const schema = layer.schema || 'public';
                  if (!layersBySchema[schema]) layersBySchema[schema] = [];
                  layersBySchema[schema].push(layer);
                });

                const sortedSchemas = Object.keys(layersBySchema).sort();

                return (
                  <div key={group.dbName} style={{ marginBottom: '15px' }}>
                    {/* Database Name */}
                    <div style={{ 
                        fontSize: '13px', 
                        fontWeight: 'bold', 
                        textTransform: 'uppercase', 
                        color: '#555',
                        marginBottom: '8px',
                        padding: '5px',
                        backgroundColor: '#eee',
                        borderRadius: '4px'
                    }}>
                      🗄️ {group.dbName}
                    </div>

                    {/* Schemas */}
                    {sortedSchemas.map(schema => {
                        // Sort Tables alphabetically
                        const sortedLayers = layersBySchema[schema].sort((a, b) => a.tableName.localeCompare(b.tableName));

                        return (
                            <div key={schema} style={{ marginLeft: '10px', marginBottom: '10px', borderLeft: '2px solid #ddd', paddingLeft: '8px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#2196F3', marginBottom: '4px' }}>
                                    Schema: {schema}
                                </div>
                                
                                {/* Layers */}
                                {sortedLayers.map(layer => {
                                    const layerId = `${group.dbName}-${layer.schema}-${layer.tableName}`;
                                    const isActive = activeVectorIds.has(layerId);
                                    const isLoading = loadingLayerId === layerId;

                                    return (
                                        <div key={layer.id} style={{ 
                                            display: 'flex', 
                                            alignItems: 'center', 
                                            padding: '6px', 
                                            borderRadius: '4px',
                                            background: isActive ? '#e3f2fd' : 'transparent',
                                            marginBottom: '2px'
                                        }}>
                                            <div style={{ flex: 1, fontSize: '13px', color: '#333' }}>
                                                {layer.tableName}
                                                <span style={{ fontSize: '10px', color: '#999', marginLeft: '5px', border: '1px solid #eee', padding: '1px 3px', borderRadius: '3px' }}>
                                                    {layer.geometryType}
                                                </span>
                                            </div>

                                            {/* Eye Button */}
                                            <button 
                                              onClick={() => toggleVectorLayerVisibility(group.dbName, layer)}
                                              disabled={isLoading}
                                              style={{ background: 'none', border: 'none', cursor: isLoading ? 'wait' : 'pointer', padding: '4px' }}
                                              title={isActive ? "Hide" : "Show"}
                                            >
                                              {isLoading ? (
                                                <div style={{ width: '16px', height: '16px', borderRadius: '50%', border: '2px solid #ccc', borderTopColor: '#2196F3', animation: 'spin 1s linear infinite' }}></div>
                                              ) : isActive ? (
                                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                  <path d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z" stroke="#2196F3" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                                  <circle cx="12" cy="12" r="3" stroke="#2196F3" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                                </svg>
                                              ) : (
                                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C5 20 1 12 1 12C1 12 2.33 9.05 4.7 7.26M1 1L23 23M9.9 4.24A9.12 9.12 0 0 1 12 4C19 4 23 12 23 12C23 12 21.93 14.51 19.9 16.24" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                                  <path d="M14.12 14.12A3 3 0 0 1 9.88 9.88" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                                </svg>
                                              )}
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        );
                    })}
                  </div>
                );
              })
            )}
          </div>
          <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* --- MAP --- */}
      <MapContainer center={[43, 47]} zoom={5} style={{ height: '100%', width: '100%' }} zoomControl={false} maxZoom={20}>
        <SetMapRef />
        <TileLayer url={baseLayer} maxZoom={20} />
        <CustomZoomControl />

        {showPanoLayer && <PanoLayer selectedMarker={selectedMarker} onMarkerClick={handleMarkerClick} />}
        
        {showOrthoLayer && selectedOrthos.map((ortho) => (
            <TileLayer key={ortho.id} url={`https://api.botplus.ru/orthophotos/${ortho.id}/tiles/{z}/{x}/{y}.png`} maxZoom={20} opacity={0.7} />
        ))}

        {/* Render active vector layers from activeVectorIds */}
        {Array.from(activeVectorIds).map((layerId) => {
          const vectorInfo = loadedVectors.get(layerId);
          if (!vectorInfo) return null;

          return (
            <GeoJSON 
              key={layerId}
              data={vectorInfo.data}
              style={getVectorStyle}
              pointToLayer={(feature, latlng) => L.marker(latlng, { icon: defaultIcon })}
              onEachFeature={(feature, layer) => {
                  if (feature.properties) {
                      const rows = Object.entries(feature.properties).map(([k, v]) => `
                          <tr style="border-bottom: 1px solid #eee;">
                              <td style="padding: 4px; font-weight: bold; color: #555;">${k}</td>
                              <td style="padding: 4px;">${v}</td>
                          </tr>
                      `).join('');
                      layer.bindPopup(`
                        <div style="font-family: sans-serif; font-size: 13px; max-height: 300px; overflow-y: auto;">
                          <h4 style="margin: 0 0 5px 0;">${vectorInfo.name}</h4>
                          <table style="width:100%; border-collapse: collapse;">${rows}</table>
                        </div>
                      `, { maxWidth: 300 });
                  }
              }}
            />
          );
        })}

        <MapClickHandler />
        <MapEventHandlers setContextMenu={setContextMenu} />
      </MapContainer>

      {showOrthoPanel && <OrthoPanel onClose={() => setShowOrthoPanel(false)} orthoImages={orthoImages} onOrthoSelect={handleOrthoSelect} selectedOrthos={selectedOrthos} fitToBounds={fitToOrthoBounds} />}
      
      {showSelectionPanel && <SelectionPanel handleSelection={() => setShowSelectionPanel(false)} closePanel={() => setShowSelectionPanel(false)} />}

      <ContextMenu contextMenu={contextMenu} handleCopyCoordinates={copyCoordinatesHandler} />
    </div>
  );
};

export default MapPage;