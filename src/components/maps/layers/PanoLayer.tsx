import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useMap, Marker } from 'react-leaflet';
import debounce from 'lodash/debounce';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { LatLngBounds, LatLng } from 'leaflet';
// Убедитесь, что этот файл существует. Если его нет, создайте или исправьте путь.
import { defaultIcon, activeIcon } from '../../icons';

interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

interface PanoramaItem {
  id: number | string;
  latitude: number;
  longitude: number;
  [key: string]: any;
}

interface PanoLayerProps {
  selectedMarker?: string | null;
  onMarkerClick?: (marker: MarkerType) => void;
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

const MIN_ZOOM_LEVEL = 10;
const MAX_MARKERS_PER_REQUEST = 1000;
const CLUSTER_SIZES = {
  far: { zoom: 10, radius: 80 },
  medium: { zoom: 14, radius: 60 },
  near: { zoom: 16, radius: 40 },
  closest: { zoom: 18, radius: 0 },
};

const PanoLayer: React.FC<PanoLayerProps> = ({
  selectedMarker = null,
  onMarkerClick,
  togglePanoLayer,
}) => {
  const [markers, setMarkers] = useState<MarkerType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadedBounds, setLoadedBounds] = useState<string[]>([]);
  const [visibleMarkers, setVisibleMarkers] = useState<MarkerType[]>([]);
  const map = useMap();

  // Определение радиуса кластеризации в зависимости от зума
  const getClusterRadius = useCallback((zoom: number) => {
    if (zoom >= CLUSTER_SIZES.closest.zoom) return CLUSTER_SIZES.closest.radius;
    if (zoom >= CLUSTER_SIZES.near.zoom) return CLUSTER_SIZES.near.radius;
    if (zoom >= CLUSTER_SIZES.medium.zoom) return CLUSTER_SIZES.medium.radius;
    return CLUSTER_SIZES.far.radius;
  }, []);

  // Фильтрация маркеров, видимых на экране
  const updateVisibleMarkers = useCallback(() => {
    if (!map) return;

    const bounds = map.getBounds();
    const zoom = map.getZoom();
    
    // Простая оптимизация: на мелких зумах показываем меньше точек
    const skipFactor = zoom < 12 ? 10 : zoom < 14 ? 5 : 1;

    const visible = markers.filter((marker, index) => {
      if (index % skipFactor !== 0) return false;
      return bounds.contains(new LatLng(marker.lat, marker.lng));
    });

    setVisibleMarkers(visible);
  }, [map, markers]);

  // Загрузка маркеров с сервера
  const fetchMarkersInBounds = useCallback(
    async (bounds: LatLngBounds) => {
      if (isLoading || !bounds) return;

      const zoom = map.getZoom();
      if (zoom < MIN_ZOOM_LEVEL) {
        setVisibleMarkers([]);
        return;
      }

      const north = bounds.getNorth();
      const south = bounds.getSouth();
      const east = bounds.getEast();
      const west = bounds.getWest();

      // Округляем границы для кэширования запросов
      const precision = zoom > 15 ? 4 : zoom > 12 ? 3 : 2;
      const boundsKey = `${north.toFixed(precision)},${south.toFixed(precision)},${east.toFixed(precision)},${west.toFixed(precision)}`;

      if (loadedBounds.includes(boundsKey)) {
        updateVisibleMarkers();
        return;
      }

      setIsLoading(true);
      try {
        const response = await fetch(
          `https://api.botplus.ru/panoramas?north=${north}&south=${south}&east=${east}&west=${west}&limit=${MAX_MARKERS_PER_REQUEST}`,
        );

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (!Array.isArray(data)) {
          console.error('Invalid data format received:', data);
          return;
        }

        const newMarkers = data
          .filter(
            (item: any): item is PanoramaItem =>
              item &&
              (typeof item.id === 'string' || typeof item.id === 'number') &&
              typeof item.latitude === 'number' &&
              typeof item.longitude === 'number',
          )
          .map((item) => ({
            id: item.id.toString(),
            lat: item.latitude,
            lng: item.longitude,
          }));

        setMarkers((prevMarkers) => {
          const existingIds = new Set(prevMarkers.map((m) => m.id));
          const uniqueNewMarkers = newMarkers.filter((m) => !existingIds.has(m.id));
          const updatedMarkers = [...prevMarkers, ...uniqueNewMarkers];

          if (togglePanoLayer) {
             togglePanoLayer(updatedMarkers);
          }

          return updatedMarkers;
        });

        setLoadedBounds((prev) => [...prev, boundsKey]);
        
        // Обновляем видимые сразу после загрузки
        requestAnimationFrame(() => {
            // updateVisibleMarkers вызываем через эффект при изменении markers, но здесь можно форсировать если нужно
        });

      } catch (error) {
        console.error('Error fetching panoramas:', error);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, map, loadedBounds, updateVisibleMarkers, togglePanoLayer],
  );

  // Debounce для предотвращения частых запросов при драге карты
  const debouncedFetchMarkers = useMemo(
    () =>
      debounce((b: LatLngBounds) => {
        fetchMarkersInBounds(b);
      }, 500),
    [fetchMarkersInBounds],
  );

  // Эффект обновления видимых маркеров при изменении полного списка
  useEffect(() => {
    updateVisibleMarkers();
  }, [markers, updateVisibleMarkers]);

  // Слушатели событий карты
  useEffect(() => {
    if (!map) return;

    const handleMoveEnd = () => {
      const bounds = map.getBounds();
      if (bounds) debouncedFetchMarkers(bounds);
    };

    const handleZoomEnd = () => {
      updateVisibleMarkers();
    };

    map.on('moveend', handleMoveEnd);
    map.on('zoomend', handleZoomEnd);

    // Первичная загрузка
    if (map.getZoom() >= MIN_ZOOM_LEVEL) {
      const initialBounds = map.getBounds();
      if (initialBounds) fetchMarkersInBounds(initialBounds);
    }

    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleZoomEnd);
      debouncedFetchMarkers.cancel();
    };
  }, [map, debouncedFetchMarkers, fetchMarkersInBounds, updateVisibleMarkers]);

  // Мемоизация кластера для предотвращения ре-рендеров
  const markerCluster = useMemo(() => {
    const zoom = map.getZoom();
    const clusterRadius = getClusterRadius(zoom);

    return (
      <MarkerClusterGroup
        key="pano-cluster" // Стабильный ключ
        disableClusteringAtZoom={CLUSTER_SIZES.closest.zoom}
        maxClusterRadius={clusterRadius}
        chunkedLoading={true}
        spiderfyOnMaxZoom={true}
        removeOutsideVisibleBounds={true}
        animate={false}
        showCoverageOnHover={false}
      >
        {visibleMarkers.map((marker) => (
          <Marker
            position={[marker.lat, marker.lng]}
            key={marker.id}
            icon={selectedMarker === marker.id ? activeIcon : defaultIcon}
            eventHandlers={{
              click: (e) => {
                // Предотвращаем всплытие, чтобы не триггерить клик по карте
                e.originalEvent.stopPropagation();
                if (onMarkerClick) onMarkerClick(marker);
              },
            }}
          />
        ))}
      </MarkerClusterGroup>
    );
  }, [visibleMarkers, selectedMarker, onMarkerClick, map, getClusterRadius]);

  return markerCluster;
};

export default PanoLayer;