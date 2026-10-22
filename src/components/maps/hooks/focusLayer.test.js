import { focusLayer } from './focusLayer';
import { useMapStore } from './useMapStore';
import { useVectorStore } from './useVectorStore';
import { workspaceRequest } from '../../../utils/workspaceApi';
jest.mock('../../../utils/workspaceApi', () => ({ workspaceRequest: jest.fn() }));
let map;
beforeEach(() => {
  jest.clearAllMocks();
  map = { fitBounds: jest.fn(), fitWorld: jest.fn() };
  useMapStore.setState({mapInstance:map,orthoImages:[{id:7,wgs84_bounds:{south:42,west:47,north:43,east:48}}]});
  useVectorStore.setState({layerSources:{roads:{dbName:'project',schema:'public',tableName:'roads'}}});
});
test('orthophoto focus uses WGS84 metadata without downloading the raster', async () => {
  await focusLayer('ortho:7');
  const b=map.fitBounds.mock.calls[0][0];
  expect(b.getWest()).toBe(47);expect(b.getNorth()).toBe(43);
  expect(workspaceRequest).not.toHaveBeenCalled();
});
test('vector focus fetches only an extent and limits zoom for single points', async () => {
  workspaceRequest.mockResolvedValue({bounds:{south:43,west:47,north:43,east:47}});
  await focusLayer('vector:roads');
  expect(workspaceRequest).toHaveBeenCalledWith('/layers/bounds?kind=vector&dbName=project&schema=public&tableName=roads');
  expect(map.fitBounds).toHaveBeenCalledWith([[43,47],[43,47]],{padding:[32,32],maxZoom:19});
});
test('a slow previous response cannot override the most recent layer click', async () => {
  let resolve;
  workspaceRequest.mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
  const pending=focusLayer('panoramas');
  await focusLayer('ortho:7');
  resolve({bounds:{south:0,west:0,north:1,east:1}});
  await pending;
  expect(map.fitBounds).toHaveBeenCalledTimes(1);
});
