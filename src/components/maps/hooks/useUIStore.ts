// src/components/maps/hooks/useUIStore.ts
import { create } from 'zustand';

// Добавлено 'pano' в список доступных панелей
export type PanelType = 'baseLayers' | 'vector' | 'ortho' | 'selection' | 'pano' | null;

interface UIState {
  activePanel: PanelType;
  setActivePanel: (panel: PanelType) => void;
  togglePanel: (panel: PanelType) => void;
  closeAll: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  activePanel: null,
  setActivePanel: (panel) => set({ activePanel: panel }),
  togglePanel: (panel) => set((state) => ({ 
    activePanel: state.activePanel === panel ? null : panel 
  })),
  closeAll: () => set({ activePanel: null }),
}));