// src/components/maps/hooks/useMapStore.ts

import { create } from 'zustand';
import L from 'leaflet';
import { fetchOrthophotos, OrthoItem } from '../../../utils/api';

// Определяем базовый URL (должен совпадать с логикой в api.ts)
const isLocalhost = typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
const API_BASE = isLocalhost ? 'http://localhost:5580' : '';

interface MapState {
  // --- Map Instance ---
  mapInstance: L.Map | null;
  setMapInstance: (map: L.Map) => void;

  // --- Base Layers ---
  baseLayerUrl: string;
  setBaseLayer: (url: string) => void;

  // --- Orthophotos ---
  orthoImages: OrthoItem[];
  selectedOrthoIds: number[];
  isLoadingOrtho: boolean;
  
  // Хранилище активных слоев Leaflet (чтобы можно было их удалять)
  activeLayers: Record<number, L.TileLayer>;

  // Actions
  fetchOrthos: () => Promise<void>;
  
  // [FIX] Обновленная сигнатура: принимаем map опционально
  toggleOrtho: (id: number, map?: L.Map | null) => void;
  
  // fitToBounds может использовать сохраненный mapInstance, аргумент map опционален
  fitToBounds: (id: number, map?: L.Map) => void;
}

export const useMapStore = create<MapState>((set, get) => ({
  mapInstance: null,
  baseLayerUrl: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  
  orthoImages: [],
  selectedOrthoIds: [],
  isLoadingOrtho: false,
  activeLayers: {},

  setMapInstance: (map) => set({ mapInstance: map }),
  
  setBaseLayer: (url) => set({ baseLayerUrl: url }),

  fetchOrthos: async () => {
    set({ isLoadingOrtho: true });
    try {
      const data = await fetchOrthophotos();
      set({ orthoImages: data });
    } catch (error) {
      console.error("Error loading orthophotos:", error);
    } finally {
      set({ isLoadingOrtho: false });
    }
  },

  toggleOrtho: (id, mapArg) => {
    const { selectedOrthoIds, orthoImages, mapInstance, activeLayers } = get();
    
    // [FIX] Используем переданную карту ИЛИ карту из стейта
    const map = mapArg || mapInstance;

    if (!map) {
      console.warn("[UseMapStore] Cannot toggle layer: Map instance is missing");
      return;
    }
    
    // 1. Если слой уже включен -> Выключаем (Удаляем)
    if (selectedOrthoIds.includes(id)) {
      const layer = activeLayers[id];
      if (layer) {
        map.removeLayer(layer);
      }
      
      const newLayers = { ...activeLayers };
      delete newLayers[id];

      set({ 
        selectedOrthoIds: selectedOrthoIds.filter(pid => pid !== id),
        activeLayers: newLayers
      });
    } 
    // 2. Если слой выключен -> Включаем (Добавляем)
    else {
      const ortho = orthoImages.find(img => img.id === id);
      if (!ortho) return;

      // Формируем URL для нашего Backend-прокси (решает CORS и доступ к MinIO)
      // Пример: http://localhost:5580/api/orthophotos/12/tiles/{z}/{x}/{y}.png
      const tileUrl = `${API_BASE}/api/orthophotos/${id}/tiles/{z}/{x}/{y}.png`;

      const newLayer = L.tileLayer(tileUrl, {
        maxZoom: 24,
        maxNativeZoom: 22, // Зависит от разрешения снимка
        attribution: 'WEAM Ortho',
        // tms: false // Для XYZ (стандарт) tms должен быть false
      });

      newLayer.addTo(map);

      set({ 
        selectedOrthoIds: [...selectedOrthoIds, id],
        activeLayers: { ...activeLayers, [id]: newLayer }
      });
    }
  },

  fitToBounds: (id, mapArg) => {
    const { orthoImages, mapInstance } = get();
    const map = mapArg || mapInstance; // Используем переданную карту или из стейта
    
    const item = orthoImages.find(img => img.id === id);
    
    if (item && item.bounds && map) {
      const { north, south, east, west } = item.bounds;
      let sw, ne;

      // Проверяем проекцию. Если это Google Maps (3857), координаты в метрах -> конвертируем в LatLng
      if (item.crs && (item.crs.includes('3857') || item.crs.includes('Pseudo-Mercator'))) {
        sw = L.CRS.EPSG3857.unproject(L.point(west, south));
        ne = L.CRS.EPSG3857.unproject(L.point(east, north));
      } 
      // Иначе считаем, что это уже LatLng (WGS84)
      else {
        sw = L.latLng(south, west);
        ne = L.latLng(north, east);
      }

      map.fitBounds(L.latLngBounds(sw, ne));
    }
  }
}));