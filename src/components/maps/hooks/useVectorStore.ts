import { create } from 'zustand';
import { fetchLayerData, VectorLayerItem } from '../../../utils/api';

interface LoadedVectorData {
  id: string;
  data: any;
  type: string;
  name: string;
}

interface VectorState {
  activeVectorIds: Set<string>;
  loadedVectors: Map<string, LoadedVectorData>;
  loadingLayerId: string | null;
  
  toggleLayer: (dbName: string, layer: VectorLayerItem) => Promise<void>;
}

export const useVectorStore = create<VectorState>((set, get) => ({
  activeVectorIds: new Set(),
  loadedVectors: new Map(),
  loadingLayerId: null,

  toggleLayer: async (dbName, layer) => {
    const { activeVectorIds, loadedVectors } = get();
    const layerId = `${dbName}-${layer.schema}-${layer.tableName}`;

    // 1. Если слой уже включен — выключаем
    if (activeVectorIds.has(layerId)) {
      const newSet = new Set(activeVectorIds);
      newSet.delete(layerId);
      set({ activeVectorIds: newSet });
      return;
    }

    // 2. Если слой выключен — включаем (проверяем кэш)
    if (loadedVectors.has(layerId)) {
      const newSet = new Set(activeVectorIds);
      newSet.add(layerId);
      set({ activeVectorIds: newSet });
    } else {
      // 3. Данных нет — загружаем
      set({ loadingLayerId: layerId });
      try {
        const geoJSON = await fetchLayerData(dbName, layer.tableName, layer.schema);
        if (geoJSON && geoJSON.features && geoJSON.features.length > 0) {
          const newData: LoadedVectorData = {
            id: layerId,
            data: geoJSON,
            type: layer.geometryType,
            name: `${layer.schema}.${layer.tableName}`
          };
          
          const newMap = new Map(loadedVectors).set(layerId, newData);
          const newSet = new Set(activeVectorIds).add(layerId);
          
          set({ loadedVectors: newMap, activeVectorIds: newSet });
        } else {
          alert(`Слой ${layer.tableName} пуст`);
        }
      } catch (error) {
        console.error(error);
        alert(`Ошибка загрузки слоя ${layer.tableName}`);
      } finally {
        set({ loadingLayerId: null });
      }
    }
  },
}));