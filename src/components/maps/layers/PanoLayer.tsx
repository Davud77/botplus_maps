import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useMap, Marker } from 'react-leaflet';
import debounce from 'lodash/debounce';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { LatLngBounds } from 'leaflet';
// Убедитесь, что этот путь верный в вашей структуре проекта
import { defaultIcon, activeIcon } from '../../icons';

// --- Типы ---
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

interface PanoLayerProps {
  selectedMarker?: string | null;
  onMarkerClick?: (marker: MarkerType) => void;
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

// --- Настройки ---
const MIN_ZOOM_LEVEL = 3; 
const MAX_MARKERS_PER_REQUEST = 1000;

// === ВАЖНОЕ ИЗМЕНЕНИЕ ===
// Устанавливаем адрес, который точно работает у вас локально
const API_ENDPOINT = '/panoramas'; 

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

  // --- Функция загрузки данных ---
  const fetchMarkersInBounds = useCallback(
    async (bounds: LatLngBounds) => {
      const zoom = map.getZoom();

      // 1. Если зум слишком мелкий, не грузим данные
      if (zoom < MIN_ZOOM_LEVEL) return;

      // 2. Формируем ключ кэша
      const precision = zoom > 15 ? 4 : 3;
      const boundsKey = `${bounds.getNorth().toFixed(precision)},${bounds.getSouth().toFixed(precision)},${bounds.getEast().toFixed(precision)},${bounds.getWest().toFixed(precision)}`;

      // 3. Если эта область уже загружена, выходим
      if (loadedBoundsRef.current.has(boundsKey)) return;

      // 4. Отменяем предыдущий запрос, если он еще висит
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        // Формируем URL
        const url = new URL(API_ENDPOINT, window.location.origin);
        
        // Добавляем параметры границ
        url.searchParams.append('north', bounds.getNorth().toString());
        url.searchParams.append('south', bounds.getSouth().toString());
        url.searchParams.append('east', bounds.getEast().toString());
        url.searchParams.append('west', bounds.getWest().toString());
        url.searchParams.append('limit', MAX_MARKERS_PER_REQUEST.toString());

        const response = await fetch(url.toString(), {
          signal: abortControllerRef.current.signal,
        });

        // 5. Защита от получения HTML вместо JSON (ваша ошибка SyntaxError)
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) {
            console.warn("API вернул HTML страницу вместо JSON. Проверьте адрес API или настройки прокси.");
            return; 
        }

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (Array.isArray(data) && data.length > 0) {
          setMarkers((prevMarkers) => {
            // Используем Map для удаления дубликатов
            const markerMap = new Map(prevMarkers.map((m) => [m.id, m]));
            let hasChanges = false;

            data.forEach((item: any) => {
              const id = String(item.id);
              // Проверяем валидность координат
              if (!markerMap.has(id) && typeof item.latitude === 'number' && typeof item.longitude === 'number') {
                markerMap.set(id, {
                  id,
                  lat: item.latitude,
                  lng: item.longitude,
                });
                hasChanges = true;
              }
            });

            if (!hasChanges) return prevMarkers;

            const updatedMarkers = Array.from(markerMap.values());
            
            // Передаем данные наверх (асинхронно)
            if (togglePanoLayer) {
               setTimeout(() => togglePanoLayer(updatedMarkers), 0);
            }

            return updatedMarkers;
          });

          // Запоминаем, что эта область загружена успешно
          loadedBoundsRef.current.add(boundsKey);
        }

      } catch (error: any) {
        // Игнорируем ошибку отмены (AbortError)
        if (error.name !== 'AbortError') {
          console.error('Error fetching panoramas:', error);
        }
      }
    },
    [map, togglePanoLayer]
  );

  // --- Debounce ---
  const debouncedFetch = useMemo(
    () =>
      debounce((bounds: LatLngBounds) => {
        fetchMarkersInBounds(bounds);
      }, 500),
    [fetchMarkersInBounds]
  );

  // --- Эффекты карты ---
  useEffect(() => {
    if (!map) return;

    const handleMapEvent = () => {
      debouncedFetch(map.getBounds());
    };

    map.on('moveend', handleMapEvent);
    map.on('zoomend', handleMapEvent);

    // Загрузка при старте
    if (map.getZoom() >= MIN_ZOOM_LEVEL) {
      handleMapEvent();
    }

    return () => {
      map.off('moveend', handleMapEvent);
      map.off('zoomend', handleMapEvent);
      debouncedFetch.cancel();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [map, debouncedFetch]);

  // --- Рендер ---
  return (
    <MarkerClusterGroup
      key="pano-cluster-group"
      chunkedLoading={true}
      spiderfyOnMaxZoom={true}
      maxClusterRadius={60}
      removeOutsideVisibleBounds={true}
      disableClusteringAtZoom={18}
      showCoverageOnHover={false}
    >
      {markers.map((marker) => (
        <Marker
          key={marker.id}
          position={[marker.lat, marker.lng]}
          icon={selectedMarker === marker.id ? activeIcon : defaultIcon}
          eventHandlers={{
            click: (e) => {
              e.originalEvent.stopPropagation();
              if (onMarkerClick) onMarkerClick(marker);
            },
          }}
        />
      ))}
    </MarkerClusterGroup>
  );
};

export default PanoLayer;