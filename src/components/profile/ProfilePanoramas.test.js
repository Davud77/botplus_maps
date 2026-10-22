import '@testing-library/jest-dom';
import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import '@testing-library/jest-dom';
import ProfilePanoramas from './ProfilePanoramas';
import {workspaceRequest} from '../../utils/workspaceApi';
let mockRole='admin';const mockFit=jest.fn();
jest.mock('../../hooks/useAuth',()=>({useAuth:()=>({user:{role:mockRole}})}));
jest.mock('react-router-dom',()=>({Link:({to,...p})=>require('react').createElement('a',{href:to,...p})}),{virtual:true});
jest.mock('react-leaflet',()=>({MapContainer:({children})=><div>{children}</div>,useMap:()=>({fitBounds:mockFit})}));
jest.mock('../maps/layers/PanoLayer',()=>({__esModule:true,default:({endpoint,query})=><div data-testid="markers">{endpoint}?{query}</div>}));
jest.mock('../maps/ui/viewers/PanoramaViewer',()=>()=>null);
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
beforeEach(()=>{jest.clearAllMocks();mockRole='admin';workspaceRequest.mockImplementation((path,method)=>Promise.resolve(method==='POST'?{status:'ok'}:path==='/media/folders'?{folders:[{id:7,name:'Съёмка'}]}:path.startsWith('/media/bounds')?{bounds:null}:{items:[{id:1,name:'one.jpg',latitude:43,longitude:47,tags:''},{id:2,name:'two.jpg',latitude:43,longitude:47,tags:''}],next_cursor:null}));});
test('page selection moves exactly selected IDs and uses reversible trash',async()=>{
 render(<ProfilePanoramas/>);fireEvent.click(await screen.findByLabelText('Выбрать страницу'));fireEvent.change(screen.getByLabelText('Папка назначения'),{target:{value:'7'}});fireEvent.click(screen.getByRole('button',{name:'Переместить',exact:true}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/bulk','POST',{ids:[1,2],action:'move',folder_id:7}));
 await waitFor(()=>expect(screen.getByLabelText('Выбрать страницу')).not.toBeChecked());fireEvent.click(screen.getByLabelText('Выбрать one.jpg'));fireEvent.click(screen.getByRole('button',{name:'В корзину'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/bulk','POST',{ids:[1],action:'trash'}));
 expect(workspaceRequest.mock.calls.some(([,method])=>method==='DELETE')).toBe(false);
});
test('map uses a bounded marker endpoint without removed filters',async()=>{
 render(<ProfilePanoramas/>);await screen.findByLabelText('Выбрать страницу');expect(screen.queryByLabelText('Поиск панорам')).toBeNull();expect(screen.queryByText('Управление папками')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Карта',exact:true}));
 expect(screen.getByTestId('markers')).toHaveTextContent('/api/media/markers?trash=0');
});
test('viewer has no bulk modification controls',async()=>{
 mockRole='viewer';render(<ProfilePanoramas/>);await screen.findByText('one.jpg');expect(screen.queryByRole('button',{name:'В корзину'})).toBeNull();expect(screen.queryByLabelText('Выбрать страницу')).toBeNull();
});
