import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import MapPreferences from './MapPreferences';
import {workspaceRequest} from '../../utils/workspaceApi';
const mockLoad=jest.fn();let mockData;
jest.mock('../../hooks/useAuth',()=>({useAuth:()=>({user:{role:'admin'},refreshUser:jest.fn()})}));
jest.mock('../../utils/mapSettings',()=>({useSettings:()=>({data:mockData,load:mockLoad})}));
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
beforeEach(()=>{mockData={coordinate_systems:[{id:'custom:stable',name:'unknown_1',definition:'',builtin:false,resolved:false}],basemaps:[],defaults:{coordinate_system:'EPSG:4326',basemap:'osm'}};mockLoad.mockResolvedValue(mockData);workspaceRequest.mockReset();workspaceRequest.mockResolvedValue({});});
test('renaming keeps the catalog identifier and does not require a CRS definition',async()=>{
 render(<MapPreferences section="crs"/>);fireEvent.click(screen.getByLabelText('Выбрать unknown_1'));fireEvent.click(screen.getByRole('button',{name:'Редактировать'}));fireEvent.change(screen.getByLabelText('Название проекции unknown_1'),{target:{value:'МСК проекта'}});fireEvent.click(screen.getByRole('button',{name:'Сохранить название'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/settings/coordinate-systems/custom%3Astable','PATCH',{name:'МСК проекта'}));expect(await screen.findByRole('status')).toHaveTextContent('Настройки сохранены.');
});

test('catalog puts the default basemap and WGS 84 first and uses table rows',()=>{
 mockData.basemaps=[{id:'other',name:'Other',url:'https://example.test/{z}/{x}/{y}',builtin:true},{id:'osm',name:'OpenStreetMap',url:'https://tile.openstreetmap.org/{z}/{x}/{y}',builtin:true}];
 mockData.coordinate_systems.push({id:'EPSG:4326',name:'WGS 84',definition:'EPSG:4326',builtin:true});
 const view=render(<MapPreferences section="basemaps"/>);
 expect(screen.getAllByRole('row')[1]).toHaveTextContent('OpenStreetMap');
 view.rerender(<MapPreferences section="crs"/>);
 expect(screen.getAllByRole('row')[1]).toHaveTextContent('WGS 84');
});
