// src/components/maps/hooks/useMapStore.ts

import { create } from 'zustand';
import L from 'leaflet';
import { fetchOrthophotos, OrthoItem } from '../../../utils/api';

interface MapState {
  // --- Map Instance ---
  mapInstance: L.Map | null;
  setMapInstance: (map: L.Map) => void;

  // --- Base Layers ---
  baseLayerUrl: string;
  baseLayerId: string;
  baseDefinition: import('../../../utils/mapSettings').Basemap | null;
  coordinateSystem: string;
  setBaseLayer: (url: string) => void;

  // --- Orthophotos ---
  orthoImages: OrthoItem[];
  selectedOrthoIds: number[];
  isLoadingOrtho: boolean;
  

  // Actions
  fetchOrthos: () => Promise<void>;
  
  // [FIX] Обновленная сигнатура: принимаем map опционально
  toggleOrtho: (id: number, map?: L.Map | null) => void;
  
  // fitToBounds может использовать сохраненный mapInstance, аргумент map опционален
  fitToBounds: (id: number, map?: L.Map) => void;
}

export const useMapStore = create<MapState>((set, get) => ({
  mapInstance: null,
  baseLayerUrl: '', baseLayerId: 'none', baseDefinition: null, coordinateSystem: 'EPSG:4326',
  
  orthoImages: [],
  selectedOrthoIds: [],
  isLoadingOrtho: false,

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

  // The React layer renderer owns all Leaflet instances.
  toggleOrtho: (id) => {
    set((state) => {
      if (!state.orthoImages.some((ortho) => ortho.id === id)) return state;
      return { selectedOrthoIds: state.selectedOrthoIds.includes(id)
        ? state.selectedOrthoIds.filter((selected) => selected !== id)
        : [...state.selectedOrthoIds, id] };
    });
  },

  fitToBounds: (id, mapArg) => {
    const { orthoImages, mapInstance } = get();
    const map = mapArg || mapInstance; // Используем переданную карту или из стейта
    
    const item = orthoImages.find(img => img.id === id);
    
    // Native bounds may be in any projected CRS. Only normalized WGS84 is safe here.
    if (item?.wgs84_bounds && map) {
      const { north, south, east, west } = item.wgs84_bounds;
      map.fitBounds(L.latLngBounds([south, west], [north, east]));
    }
  }
}));