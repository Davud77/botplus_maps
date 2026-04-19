// src/components/maps/layers/PanoLayer.tsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useMap, Marker, CircleMarker } from 'react-leaflet';
import debounce from 'lodash/debounce';
import L, { LatLngBounds } from 'leaflet';

// --- Типы ---
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
  count: number; 
}

interface PanoLayerProps {
  selectedMarker?: string | null;
  onMarkerClick?: (marker: MarkerType) => void;
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

const MIN_ZOOM_LEVEL = 3; 
const MAX_MARKERS_PER_REQUEST = 50000; 
const API_ENDPOINT = '/api/panoramas'; 

// Красивая и независимая иконка для серверного кластера
const createClusterIcon = (count: number) => {
  let size = 40;
  let bgColor = 'rgba(110, 204, 57, 0.7)'; // Зеленый
  let borderColor = 'rgba(110, 204, 57, 1)';

  if (count > 100) {
    size = 46;
    bgColor = 'rgba(240, 194, 12, 0.8)'; // Желтый
    borderColor = 'rgba(240, 194, 12, 1)';
  }
  if (count > 1000) {
    size = 54;
    bgColor = 'rgba(241, 128, 23, 0.8)'; // Оранжевый
    borderColor = 'rgba(241, 128, 23, 1)';
  }

  const html = `
    <div style="
      background-color: ${bgColor};
      border: 2px solid ${borderColor};
      width: ${size}px;
      height: ${size}px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      text-shadow: 0px 1px 2px rgba(0,0,0,0.8);
      font-weight: bold;
      font-family: Arial, sans-serif;
      font-size: 13px;
      box-shadow: 0 3px 6px rgba(0,0,0,0.3);
    ">
      ${count > 9999 ? '10k+' : count}
    </div>
  `;

  return L.divIcon({
    html,
    className: '', // Убрали сторонние классы
    iconSize: L.point(size, size),
    iconAnchor: L.point(size / 2, size / 2),
  });
};

const PanoLayer: React.FC<PanoLayerProps> = ({
  selectedMarker = null,
  onMarkerClick,
  togglePanoLayer,
}) => {
  const [markers, setMarkers] = useState<MarkerType[]>([]);
  const map = useMap();

  const abortControllerRef = useRef<AbortController | null>(null);

  // --- Функция загрузки данных ---
  const fetchMarkersInBounds = useCallback(
    async (bounds: LatLngBounds, currentZoom: number) => {
      if (currentZoom < MIN_ZOOM_LEVEL) {
        setMarkers([]);
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        const url = new URL(API_ENDPOINT, window.location.origin);
        
        // Берем область карты с запасом 20%, чтобы не было резких пропаданий при сдвиге
        const paddedBounds = bounds.pad(0.2);

        url.searchParams.append('north', paddedBounds.getNorth().toString());
        url.searchParams.append('south', paddedBounds.getSouth().toString());
        url.searchParams.append('east', paddedBounds.getEast().toString());
        url.searchParams.append('west', paddedBounds.getWest().toString());
        url.searchParams.append('zoom', currentZoom.toString());
        url.searchParams.append('limit', MAX_MARKERS_PER_REQUEST.toString());

        const response = await fetch(url.toString(), {
          signal: abortControllerRef.current.signal,
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) return; 

        if (!response.ok) throw new Error(`HTTP error`);

        const data = await response.json();

        if (Array.isArray(data)) {
          const updatedMarkers = data
            .filter((item: any) => typeof item.latitude === 'number' && typeof item.longitude === 'number')
            .map((item: any) => ({
              id: String(item.id),
              lat: item.latitude,
              lng: item.longitude,
              count: item.count || 1,
            }));

          // ПОЛНАЯ ЗАМЕНА СОСТОЯНИЯ (Без бесконечного накопления)
          setMarkers(updatedMarkers);
          
          if (togglePanoLayer) {
             setTimeout(() => togglePanoLayer(updatedMarkers), 0);
          }
        }
      } catch (error: any) {
        if (error.name !== 'AbortError') console.error('Error fetching panoramas:', error);
      }
    },
    [togglePanoLayer]
  );

  // --- Debounce ---
  const debouncedFetch = useMemo(
    () => debounce((bounds: LatLngBounds, zoom: number) => {
        fetchMarkersInBounds(bounds, zoom);
    }, 300), // Уменьшили задержку для большей отзывчивости
    [fetchMarkersInBounds]
  );

  // --- Эффекты карты ---
  useEffect(() => {
    if (!map) return;

    const handleMapEvent = () => {
      debouncedFetch(map.getBounds(), map.getZoom());
    };

    map.on('moveend', handleMapEvent);
    map.on('zoomend', handleMapEvent);

    if (map.getZoom() >= MIN_ZOOM_LEVEL) handleMapEvent();

    return () => {
      map.off('moveend', handleMapEvent);
      map.off('zoomend', handleMapEvent);
      debouncedFetch.cancel();
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, [map, debouncedFetch]);

  // --- Рендер ---
  return (
    <React.Fragment>
      {markers.map((marker) => {
        // 1. Если сервер вернул кластер
        if (marker.count > 1) {
          return (
            <Marker
              key={`cluster-${marker.id}-${marker.lat}-${marker.lng}`}
              position={[marker.lat, marker.lng]}
              icon={createClusterIcon(marker.count)}
              eventHandlers={{
                click: (e) => {
                  L.DomEvent.stopPropagation(e);
                  // Приближаем карту ровно в центр кластера
                  map.setView([marker.lat, marker.lng], map.getZoom() + 2);
                },
              }}
            />
          );
        }

        // 2. Если сервер вернул сырую точку (Зум 18-23). 
        // Используем Canvas (CircleMarker), он работает в 100 раз быстрее обычного DOM Marker.
        return (
          <CircleMarker
            key={`raw-${marker.id}`}
            center={[marker.lat, marker.lng]}
            radius={6} // Размер точки
            pathOptions={{
              fillColor: selectedMarker === marker.id ? '#ff3b30' : '#2db7f5', // Красный при выборе, иначе голубой
              color: '#ffffff', // Белая обводка
              weight: 1.5,
              fillOpacity: 1
            }}
            eventHandlers={{
              click: (e) => {
                L.DomEvent.stopPropagation(e);
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