import { useMapStore } from './useMapStore';
import { useVectorStore } from './useVectorStore';

describe('layer activation stays independent of bulk data downloads', () => {
  let previousFetch;
  beforeEach(() => {
    previousFetch = global.fetch;
    global.fetch = jest.fn(() => Promise.reject(new Error('Layer activation must not fetch geometry')));
    useMapStore.setState({ selectedOrthoIds: [], orthoImages: [{ id: 7, filename: 'ortho.tif' }] });
    useVectorStore.setState({ activeVectorIds: new Set() });
  });
  afterEach(() => { global.fetch = previousFetch; });

  test('orthophoto selection does not create imperative layers alongside React layers', () => {
    const map = { addLayer: jest.fn(), removeLayer: jest.fn() };
    useMapStore.getState().toggleOrtho(7, map);
    expect(useMapStore.getState().selectedOrthoIds).toEqual([7]);
    useMapStore.getState().toggleOrtho(7, map);
    expect(useMapStore.getState().selectedOrthoIds).toEqual([]);
    expect(map.addLayer).not.toHaveBeenCalled();
    expect(map.removeLayer).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('concurrent vector selections do not overwrite one another or prefetch GeoJSON', async () => {
    const layer = (tableName) => ({ schema: 'public', tableName, geometryType: 'POLYGON' });
    await Promise.all([
      useVectorStore.getState().toggleLayer('project', layer('first')),
      useVectorStore.getState().toggleLayer('project', layer('second')),
    ]);
    expect([...useVectorStore.getState().activeVectorIds].sort()).toEqual([
      'project-public-first', 'project-public-second',
    ]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('fit-to-data uses WGS84 footprint instead of treating local CRS metres as degrees', () => {
    const map = { fitBounds: jest.fn() };
    useMapStore.setState({ orthoImages: [{ id: 7, crs: 'Local CRS',
      bounds: { west: 1000000, east: 1000100, south: 2000000, north: 2000100 },
      wgs84_bounds: { west: 47, east: 48, south: 42, north: 43 } }] });
    useMapStore.getState().fitToBounds(7, map);
    const bounds = map.fitBounds.mock.calls[0][0];
    expect(bounds.getWest()).toBe(47);
    expect(bounds.getNorth()).toBe(43);
  });
});
