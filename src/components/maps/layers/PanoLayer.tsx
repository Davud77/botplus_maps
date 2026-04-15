// src/components/maps/layers/PanoLayer.tsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useMap, Marker } from 'react-leaflet';
import debounce from 'lodash/debounce';
import L, { LatLngBounds } from 'leaflet';
// Убедитесь, что этот путь верный в вашей структуре проекта
import { defaultIcon, activeIcon } from '../../icons';

// --- Типы ---
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
  count: number; // Количество панорам (от сервера)
}

interface PanoLayerProps {
  selectedMarker?: string | null;
  onMarkerClick?: (marker: MarkerType) => void;
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

// --- Настройки ---
const MIN_ZOOM_LEVEL = 3; 
const MAX_MARKERS_PER_REQUEST = 50000; 

const API_ENDPOINT = '/api/panoramas'; 

// Вспомогательная функция для генерации иконки серверного кластера
const createClusterIcon = (count: number) => {
  let sizeClass = 'marker-cluster-small';
  if (count > 100) sizeClass = 'marker-cluster-medium';
  if (count > 1000) sizeClass = 'marker-cluster-large';

  return L.divIcon({
    html: `<div><span>${count}</span></div>`,
    className: `marker-cluster ${sizeClass}`,
    iconSize: L.point(40, 40)
  });
};

const PanoLayer: React.FC<PanoLayerProps> = ({
  selectedMarker = null,
  onMarkerClick,
  togglePanoLayer,
}) => {
  const [markers, setMarkers] = useState<MarkerType[]>([]);
  const map = useMap();

  // Refs для управления запросами без ре-рендеров
  const abortControllerRef = useRef<AbortController | null>(null);
  const loadedBoundsRef = useRef<Set<string>>(new Set());
  const lastZoomRef = useRef<number>(map.getZoom());

  // --- Функция загрузки данных ---
  const fetchMarkersInBounds = useCallback(
    async (bounds: LatLngBounds, currentZoom: number) => {
      if (currentZoom < MIN_ZOOM_LEVEL) {
        setMarkers([]);
        return;
      }

      const precision = currentZoom > 15 ? 4 : 3;
      const boundsKey = `${currentZoom}_${bounds.getNorth().toFixed(precision)}_${bounds.getSouth().toFixed(precision)}_${bounds.getEast().toFixed(precision)}_${bounds.getWest().toFixed(precision)}`;

      if (loadedBoundsRef.current.has(boundsKey)) return;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        const url = new URL(API_ENDPOINT, window.location.origin);
        
        url.searchParams.append('north', bounds.getNorth().toString());
        url.searchParams.append('south', bounds.getSouth().toString());
        url.searchParams.append('east', bounds.getEast().toString());
        url.searchParams.append('west', bounds.getWest().toString());
        url.searchParams.append('zoom', currentZoom.toString()); 
        url.searchParams.append('limit', MAX_MARKERS_PER_REQUEST.toString());

        const response = await fetch(url.toString(), {
          signal: abortControllerRef.current.signal,
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) {
            console.warn("API вернул HTML страницу вместо JSON.");
            return; 
        }

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (Array.isArray(data)) {
          setMarkers((prevMarkers) => {
            const markerMap = new Map(prevMarkers.map((m) => [m.id, m]));
            let hasChanges = false;

            data.forEach((item: any) => {
              const id = String(item.id);
              if (!markerMap.has(id) && typeof item.latitude === 'number' && typeof item.longitude === 'number') {
                markerMap.set(id, {
                  id,
                  lat: item.latitude,
                  lng: item.longitude,
                  count: item.count || 1,
                });
                hasChanges = true;
              }
            });

            if (!hasChanges) return prevMarkers;

            const updatedMarkers = Array.from(markerMap.values());
            if (togglePanoLayer) {
               setTimeout(() => togglePanoLayer(updatedMarkers), 0);
            }
            return updatedMarkers;
          });

          loadedBoundsRef.current.add(boundsKey);
        }

      } catch (error: any) {
        if (error.name !== 'AbortError') {
          console.error('Error fetching panoramas:', error);
        }
      }
    },
    [togglePanoLayer]
  );

  // --- Debounce ---
  const debouncedFetch = useMemo(
    () =>
      debounce((bounds: LatLngBounds, zoom: number) => {
        fetchMarkersInBounds(bounds, zoom);
      }, 500),
    [fetchMarkersInBounds]
  );

  // --- Эффекты карты ---
  useEffect(() => {
    if (!map) return;

    // Срабатывает при перемещении карты (без смены зума)
    const handleMoveEnd = () => {
      debouncedFetch(map.getBounds(), map.getZoom());
    };

    // Срабатывает при изменении масштаба
    const handleZoomEnd = () => {
      const currentZoom = map.getZoom();
      
      // Если зум изменился, полностью очищаем кэш и старые маркеры, 
      // чтобы кластеры предыдущего масштаба не смешивались с новыми.
      if (currentZoom !== lastZoomRef.current) {
        loadedBoundsRef.current.clear();
        setMarkers([]); 
        lastZoomRef.current = currentZoom;
      }
      
      debouncedFetch(map.getBounds(), currentZoom);
    };

    map.on('moveend', handleMoveEnd);
    map.on('zoomend', handleZoomEnd);

    // Загрузка при старте
    if (map.getZoom() >= MIN_ZOOM_LEVEL) {
      handleZoomEnd();
    }

    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleZoomEnd);
      debouncedFetch.cancel();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [map, debouncedFetch]);

  // --- Рендер ---
  // Нам больше не нужен MarkerClusterGroup. Мы просто рендерим то, что отдал сервер.
  return (
    <React.Fragment>
      {markers.map((marker) => {
        // 1. Серверный кластер (сгруппированные точки)
        if (marker.count > 1) {
          return (
            <Marker
              key={`cluster-${marker.id}`}
              position={[marker.lat, marker.lng]}
              icon={createClusterIcon(marker.count)}
              eventHandlers={{
                click: (e) => {
                  e.originalEvent.stopPropagation();
                  // При клике на кластер приближаем карту
                  map.setView([marker.lat, marker.lng], map.getZoom() + 2);
                },
              }}
            />
          );
        } 
        
        // 2. Обычный маркер (сырая точка)
        return (
          <Marker
            key={`marker-${marker.id}`}
            position={[marker.lat, marker.lng]}
            icon={selectedMarker === marker.id ? activeIcon : defaultIcon}
            eventHandlers={{
              click: (e) => {
                e.originalEvent.stopPropagation();
                if (onMarkerClick) onMarkerClick(marker);
              },
            }}
          />
        );
      })}
    </React.Fragment>
  );
};

export default PanoLayer;