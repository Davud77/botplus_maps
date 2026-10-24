import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,act,fireEvent} from '@testing-library/react';
import L from 'leaflet';
import PanoLayer from './PanoLayer';
let mockZoom=14;const mockListeners={};
const mockMap={getBounds:()=>L.latLngBounds([[42.99,46.99],[43.01,47.01]]),getZoom:()=>mockZoom,getMaxZoom:()=>22,on:(name,fn)=>{mockListeners[name]=fn;},off:jest.fn(),flyTo:jest.fn()};
jest.mock('react-leaflet',()=>({useMap:()=>mockMap,CircleMarker:()=> <i data-testid="point"/>,Polyline:({positions,pathOptions,eventHandlers})=><button data-testid="coverage" data-color={pathOptions.color} data-weight={pathOptions.weight} onClick={()=>eventHandlers.click({latlng:{lat:43,lng:47}})}>{positions.length}</button>}));
beforeEach(()=>{jest.useFakeTimers();mockZoom=14;mockMap.flyTo.mockClear();global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.includes('/coverage')?{type:'LineString',coordinates:[[47,43],[47.001,43]]}:[{id:1,lat:43,lng:47,count:10,cluster:true},{id:2,lat:43,lng:47,count:1}]}));});
afterEach(()=>{jest.useRealTimers();jest.restoreAllMocks();});
test('coverage uses contrasting strokes, zooms to points on click, and reuses geometry during zoom',async()=>{
 const view=render(<PanoLayer/>);
 await act(async()=>{jest.advanceTimersByTime(300);});
 const lines=screen.getAllByTestId('coverage');expect(lines).toHaveLength(2);expect(lines[0]).toHaveAttribute('data-color','#ffffff');expect(lines[0]).toHaveAttribute('data-weight','8');
 expect(screen.queryByTestId('point')).toBeNull();expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.click(lines[1]);expect(mockMap.flyTo).toHaveBeenCalledWith({lat:43,lng:47},18,expect.objectContaining({animate:true}));
 mockZoom=16;await act(async()=>{mockListeners.zoomstart();mockListeners.zoomend();jest.advanceTimersByTime(300);});expect(fetch).toHaveBeenCalledTimes(1);
 mockZoom=19;await act(async()=>{mockListeners.zoomend();jest.advanceTimersByTime(300);});
 expect(screen.queryByTestId('coverage')).toBeNull();expect(screen.getAllByTestId('point')).toHaveLength(1);expect(fetch.mock.calls.at(-1)[0]).toContain('points=1');
 const signal=fetch.mock.calls.at(-1)[1].signal;view.unmount();expect(signal.aborted).toBe(true);
});
test('panorama style and threshold apply without refetching lines',async()=>{
 const view=render(<PanoLayer options={{color:'#112233',outlineWidth:0,pointZoom:20}}/>);await act(async()=>{jest.advanceTimersByTime(300);});
 expect(screen.getAllByTestId('coverage')).toHaveLength(1);expect(screen.getByTestId('coverage')).toHaveAttribute('data-color','#112233');
 view.rerender(<PanoLayer options={{color:'#445566',outlineWidth:3,pointZoom:20}}/>);expect(screen.getAllByTestId('coverage')).toHaveLength(2);expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.click(screen.getAllByTestId('coverage')[1]);expect(mockMap.flyTo.mock.calls[0][1]).toBe(20);
});

test('returning from world scale restores cached coverage',async()=>{
 mockZoom=3;render(<PanoLayer/>);await act(async()=>{jest.advanceTimersByTime(300);});expect(screen.getAllByTestId('coverage')).toHaveLength(2);
 mockZoom=2;await act(async()=>{mockListeners.zoomend();jest.advanceTimersByTime(300);});expect(screen.queryByTestId('coverage')).toBeNull();
 mockZoom=3;await act(async()=>{mockListeners.zoomend();jest.advanceTimersByTime(300);});expect(screen.getAllByTestId('coverage')).toHaveLength(2);
});

test('public layer uses only publication-scoped coverage and point endpoints',async()=>{
 render(<PanoLayer publicView endpoint="/api/public/maps/shared/panoramas" coverageEndpoint="/api/public/maps/shared/panoramas/coverage"/>);
 await act(async()=>{jest.advanceTimersByTime(300);});expect(fetch.mock.calls[0][0]).toContain('/api/public/maps/shared/panoramas/coverage?');
 mockZoom=19;await act(async()=>{mockListeners.zoomend();jest.advanceTimersByTime(300);});
 expect(fetch.mock.calls[1][0]).toContain('/api/public/maps/shared/panoramas?');expect(fetch.mock.calls.every(([url])=>url.startsWith('/api/public/maps/shared/'))).toBe(true);
});
