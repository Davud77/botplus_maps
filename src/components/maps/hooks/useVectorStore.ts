import { create } from 'zustand';
import { VectorSource } from '../../../utils/workspaceApi';
import { VectorLayerItem } from '../../../utils/api';

interface VectorState {
  activeVectorIds: Set<string>;
  layerSources: Record<string, VectorSource>;
  loadingLayerId: string | null;
  toggleLayer: (dbName: string, layer: VectorLayerItem) => Promise<void>;
}

export const useVectorStore = create<VectorState>((set) => ({
  activeVectorIds: new Set(),
  layerSources: {},
  loadingLayerId: null,
  // Activation uses catalog metadata. Geometry is fetched by the tile renderer only.
  toggleLayer: async (dbName, layer) => {
    const layerId = `${dbName}-${layer.schema}-${layer.tableName}`;
    set((state) => {
      const next = new Set(state.activeVectorIds);
      if (next.has(layerId)) next.delete(layerId);
      else next.add(layerId);
      return { activeVectorIds: next, layerSources: { ...state.layerSources, [layerId]: { dbName, schema: layer.schema, tableName: layer.tableName } } };
    });
  },
}));
