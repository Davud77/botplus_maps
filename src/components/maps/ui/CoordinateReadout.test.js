import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,act} from '@testing-library/react';
import {CoordinateReadout} from './CoordinateReadout';
let mockZoom=16;const mockEvents={};const mockMap={getCenter:()=>({wrap:()=>({lat:43,lng:47})}),getZoom:()=>mockZoom,on:(name,fn)=>{mockEvents[name]=fn;},off:jest.fn()};
jest.mock('react-leaflet',()=>({useMap:()=>mockMap}));
jest.mock('../hooks/useMapStore',()=>({useMapStore:fn=>fn({coordinateSystem:'EPSG:4326'})}));
jest.mock('../../../utils/mapSettings',()=>({useSettings:fn=>fn({data:null})}));
jest.mock('../../../utils/workspaceApi',()=>({workspaceRequest:()=>Promise.resolve({x:47,y:43,unit:'°',name:'WGS 84'})}));
test('coordinate readout shows the current zoom and updates after zooming',async()=>{
 render(<CoordinateReadout/>);await screen.findByText(/WGS 84/);expect(screen.getByText('· Z: 16')).toBeInTheDocument();
 await act(async()=>{mockZoom=18.5;await mockEvents.zoomend();});expect(screen.getByText('· Z: 18.5')).toBeInTheDocument();
});
