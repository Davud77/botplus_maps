import { create } from 'zustand';
import { fetchOrthophotos, OrthoItem } from '../../../utils/api';
// Для Leaflet типов, если используем L
import L from 'leaflet'; 

interface MapState {
  // --- Base Layers ---
  baseLayerUrl: string;
  setBaseLayer: (url: string) => void;

  // --- Orthophotos ---
  orthoImages: OrthoItem[];
  selectedOrthoIds: number[];
  isLoadingOrtho: boolean;
  
  // Actions
  fetchOrthos: () => Promise<void>;
  toggleOrtho: (id: number) => void;
  // Fit Bounds требует инстанс карты, передаем его аргументом
  fitToBounds: (id: number, map: L.Map) => void;
}

export const useMapStore = create<MapState>((set, get) => ({
  baseLayerUrl: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  
  setBaseLayer: (url) => set({ baseLayerUrl: url }),

  orthoImages: [],
  selectedOrthoIds: [],
  isLoadingOrtho: false,

  fetchOrthos: async () => {
    if (get().orthoImages.length > 0) return;

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

  toggleOrtho: (id) => {
    const { selectedOrthoIds } = get();
    if (selectedOrthoIds.includes(id)) {
      set({ selectedOrthoIds: selectedOrthoIds.filter(pid => pid !== id) });
    } else {
      set({ selectedOrthoIds: [...selectedOrthoIds, id] });
    }
  },

  fitToBounds: (id, map) => {
    const item = get().orthoImages.find(img => img.id === id);
    if (item && item.bounds && map) {
      // Используем L напрямую или через dynamic import если нужно
      // Здесь предполагаем, что L доступен глобально или импортирован
      const sw = L.CRS.EPSG3857.unproject(L.point(item.bounds.west, item.bounds.south));
      const ne = L.CRS.EPSG3857.unproject(L.point(item.bounds.east, item.bounds.north));
      map.fitBounds(L.latLngBounds(sw, ne));
    }
  }
}));