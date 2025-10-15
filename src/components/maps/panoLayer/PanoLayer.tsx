import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useMap } from 'react-leaflet';
import debounce from 'lodash/debounce';
import { Marker } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { defaultIcon, activeIcon } from '../../icons';
import { LatLngBounds, LatLng } from 'leaflet';

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
  /** Можно не передавать — тогда все маркеры будут в обычном состоянии */
  selectedMarker?: string | null;
  /** Можно не передавать — клики по маркерам просто игнорируются */
  onMarkerClick?: (marker: MarkerType) => void;
  /** Доп. колбэк: уведомить родителя о новом наборе маркеров (опционально) */
  togglePanoLayer?: (newMarkers: MarkerType[]) => void;
}

// Константы для оптимизации
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

  const getClusterRadius = useCallback((zoom: number) => {
    if (zoom >= CLUSTER_SIZES.closest.zoom) return CLUSTER_SIZES.closest.radius;
    if (zoom >= CLUSTER_SIZES.near.zoom) return CLUSTER_SIZES.near.radius;
    if (zoom >= CLUSTER_SIZES.medium.zoom) return CLUSTER_SIZES.medium.radius;
    return CLUSTER_SIZES.far.radius;
  }, []);

  const updateVisibleMarkers = useCallback(() => {
    if (!map) return;

    const bounds = map.getBounds();
    const zoom = map.getZoom();
    const skipFactor = zoom < 12 ? 10 : zoom < 14 ? 5 : 1;

    const visible = markers.filter((marker, index) => {
      if (index % skipFactor !== 0) return false;
      return bounds.contains(new LatLng(marker.lat, marker.lng));
    });

    setVisibleMarkers(visible);
  }, [map, markers]);

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

          // Уведомим родителя, если передан колбэк
          try {
            if (togglePanoLayer) togglePanoLayer(updatedMarkers);
          } catch (e) {
            console.error('togglePanoLayer callback failed:', e);
          }

          // Обновляем видимые маркеры после добавления новых
          requestAnimationFrame(() => {
            updateVisibleMarkers();
          });

          return updatedMarkers;
        });

        setLoadedBounds((prev) => [...prev, boundsKey]);
      } catch (error) {
        console.error('Error fetching panoramas:', error);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, map, loadedBounds, updateVisibleMarkers, togglePanoLayer],
  );

  const debouncedFetchMarkers = useMemo(
    () =>
      debounce((b: LatLngBounds) => {
        fetchMarkersInBounds(b);
      }, 1000),
    [fetchMarkersInBounds],
  );

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

  const markerCluster = useMemo(() => {
    const zoom = map.getZoom();
    const clusterRadius = getClusterRadius(zoom);

    return (
      <MarkerClusterGroup
        disableClusteringAtZoom={CLUSTER_SIZES.closest.zoom}
        maxClusterRadius={clusterRadius}
        chunkedLoading={true}
        spiderfyOnMaxZoom={true}
        removeOutsideVisibleBounds={true}
        animate={false}
      >
        {visibleMarkers.map((marker) => (
          <Marker
            position={[marker.lat, marker.lng]}
            key={marker.id}
            icon={selectedMarker === marker.id ? activeIcon : defaultIcon}
            eventHandlers={{
              click: () => {
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
