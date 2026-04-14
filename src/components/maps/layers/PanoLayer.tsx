// src/components/maps/layers/PanoLayer.tsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useMap, Marker } from 'react-leaflet';
import debounce from 'lodash/debounce';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L, { LatLngBounds } from 'leaflet';
// Убедитесь, что этот путь верный в вашей структуре проекта
import { defaultIcon, activeIcon } from '../../icons';

// --- Типы ---
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
  count: number; // Новое поле: количество панорам в кластере (от сервера)
}

interface PanoLayerProps {
  selectedMarker?: string | null;
  onMarkerClick?: (marker: MarkerType) => void;
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

// --- Настройки ---
const MIN_ZOOM_LEVEL = 3; 
// Лимит можно смело уменьшить, так как серверная кластеризация не даст вернуть 100к точек
const MAX_MARKERS_PER_REQUEST = 10000; 

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

  // --- Функция загрузки данных ---
  const fetchMarkersInBounds = useCallback(
    async (bounds: LatLngBounds, currentZoom: number) => {
      // 1. Если зум слишком мелкий, не грузим данные
      if (currentZoom < MIN_ZOOM_LEVEL) return;

      // 2. Формируем ключ кэша (добавляем зум, так как кластеры зависят от зума)
      const precision = currentZoom > 15 ? 4 : 3;
      const boundsKey = `${currentZoom}_${bounds.getNorth().toFixed(precision)}_${bounds.getSouth().toFixed(precision)}_${bounds.getEast().toFixed(precision)}_${bounds.getWest().toFixed(precision)}`;

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
        
        // Добавляем параметры границ и текущий зум
        url.searchParams.append('north', bounds.getNorth().toString());
        url.searchParams.append('south', bounds.getSouth().toString());
        url.searchParams.append('east', bounds.getEast().toString());
        url.searchParams.append('west', bounds.getWest().toString());
        url.searchParams.append('zoom', currentZoom.toString()); // <-- Передаем зум на сервер
        url.searchParams.append('limit', MAX_MARKERS_PER_REQUEST.toString());

        const response = await fetch(url.toString(), {
          signal: abortControllerRef.current.signal,
        });

        // 5. Защита от получения HTML вместо JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) {
            console.warn("API вернул HTML страницу вместо JSON. Проверьте адрес API или настройки прокси.");
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
              // Проверяем валидность координат
              if (!markerMap.has(id) && typeof item.latitude === 'number' && typeof item.longitude === 'number') {
                markerMap.set(id, {
                  id,
                  lat: item.latitude,
                  lng: item.longitude,
                  count: item.count || 1, // Читаем count из ответа сервера (по умолчанию 1)
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

    const handleMapEvent = () => {
      // Передаем и границы, и текущий зум
      debouncedFetch(map.getBounds(), map.getZoom());
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


  // --- Разделяем маркеры на сырые (одиночные) и серверные кластеры ---
  const rawMarkers = markers.filter(m => m.count === 1);
  const serverClusters = markers.filter(m => m.count > 1);

  // --- Рендер ---
  return (
    <React.Fragment>
      {/* 1. Отрисовка Серверных Кластеров (count > 1) */}
      {serverClusters.map((cluster) => (
        <Marker
          key={`cluster-${cluster.id}`}
          position={[cluster.lat, cluster.lng]}
          icon={createClusterIcon(cluster.count)}
          eventHandlers={{
            click: (e) => {
              e.originalEvent.stopPropagation();
              // При клике на серверный кластер - приближаем карту
              map.setView([cluster.lat, cluster.lng], map.getZoom() + 2);
            },
          }}
        />
      ))}

      {/* 2. Отрисовка обычных маркеров через MarkerClusterGroup 
          (на случай если одиночные маркеры всё-таки стоят вплотную на крупном масштабе) */}
      <MarkerClusterGroup
        key="pano-cluster-group"
        chunkedLoading={true}
        spiderfyOnMaxZoom={true}
        maxClusterRadius={60}
        removeOutsideVisibleBounds={true}
        disableClusteringAtZoom={18}
        showCoverageOnHover={false}
      >
        {rawMarkers.map((marker) => (
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
        ))}
      </MarkerClusterGroup>
    </React.Fragment>
  );
};

export default PanoLayer;