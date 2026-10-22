import { useMapStore } from './useMapStore';
import { useVectorStore } from './useVectorStore';
import { workspaceRequest, VectorSource } from '../../../utils/workspaceApi';
let focusSequence = 0;

export async function focusLayer(key: string, vectorSource?: VectorSource): Promise<void> {
  const sequence = ++focusSequence;
  const state = useMapStore.getState();
  const map = state.mapInstance;
  if (!map) return;
  if (key.startsWith('ortho:')) {
    const id = Number(key.slice(6));
    if (!state.orthoImages.find(item => item.id === id)?.wgs84_bounds) throw new Error('Границы ортофотоплана недоступны.');
    state.fitToBounds(id);
    return;
  }
  if (key === 'basemap') {
    map.fitWorld();
    return;
  }
  let query: URLSearchParams;
  if (key === 'panoramas') query = new URLSearchParams({ kind: 'panoramas' });
  else {
    const source = vectorSource || useVectorStore.getState().layerSources[key.slice(7)];
    if (!source) throw new Error('Источник слоя недоступен.');
    query = new URLSearchParams({ kind: 'vector', ...source });
  }
  const { bounds } = await workspaceRequest<{ bounds: { west: number; south: number; east: number; north: number } | null }>(`/layers/bounds?${query}`);
  if (!bounds) throw new Error('В слое пока нет объектов.');
  // Ignore responses for a map that was closed while the request was pending.
  if (useMapStore.getState().mapInstance !== map || sequence !== focusSequence) return;
  map.fitBounds([[bounds.south, bounds.west], [bounds.north, bounds.east]], { padding: [32, 32], maxZoom: 19 });
}
