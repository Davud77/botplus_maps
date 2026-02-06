import { create } from 'zustand';

export type PanelType = 'baseLayers' | 'vector' | 'ortho' | 'selection' | null;

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