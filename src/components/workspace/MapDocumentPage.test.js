import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import MapDocumentPage from './MapDocumentPage';
import {workspaceRequest} from '../../utils/workspaceApi';
const mockNavigate=jest.fn();
const mockState={orthoImages:[],fetchOrthos:jest.fn(()=>Promise.resolve()),selectedOrthoIds:[],baseLayerId:'osm',coordinateSystem:'EPSG:4326'};
jest.mock('react-router-dom',()=>({useNavigate:()=>mockNavigate,useParams:()=>({mapId:'map-1'}),Link:({to,...props})=>require('react').createElement('a',{href:to,...props})}),{virtual:true});
jest.mock('../../utils/workspaceApi',()=>({...jest.requireActual('../../utils/workspaceApi'),workspaceRequest:jest.fn()}));
jest.mock('../maps/hooks/useMapStore',()=>({useMapStore:{getState:()=>mockState,setState:jest.fn()}}));
jest.mock('../maps/MapPage',()=>props=><>{props.documentControls}{props.diagnostics&&<div className="bp-raster-status">Диагностика активна</div>}</>);
let record;
beforeEach(()=>{jest.clearAllMocks();record={id:'map-1',title:'Участок',description:'Существующее описание',revision:3,can_edit:true,published:false,config:{orthophoto_ids:[],vector_layers:[],base_layer:'osm',view:{center:[43,47],zoom:5},show_panoramas:false}};workspaceRequest.mockImplementation((path,method,body)=>Promise.resolve({map:method==='PUT'?{...record,...body}:record}));});
test('description lives in settings, diagnostics is opt-in and deletion uses the revision',async()=>{
 const confirm=jest.spyOn(window,'confirm').mockReturnValue(true);const view=render(<MapDocumentPage/>);
 await screen.findByDisplayValue('Участок');expect(view.container.querySelector('.bp-raster-status')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Диагностика'}));expect(view.container.querySelector('.bp-raster-status')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Описание карты'),{target:{value:'Новое описание'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить карту'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/maps/map-1','PUT',expect.objectContaining({description:'Новое описание',revision:3})));
 await screen.findByRole('button',{name:'Сохранить карту'});
 fireEvent.click(screen.getByRole('button',{name:'Удалить карту'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/maps/map-1','DELETE',{revision:3}));
 expect(mockNavigate).toHaveBeenCalledWith('/');confirm.mockRestore();
});
test('a viewer reads the description and can diagnose but cannot delete the map',async()=>{
 record.can_edit=false;render(<MapDocumentPage/>);await screen.findByText('Существующее описание');
 expect(screen.queryByRole('button',{name:'Удалить карту'})).toBeNull();expect(screen.getByRole('button',{name:'Диагностика'})).toBeEnabled();
});

afterEach(()=>jest.useRealTimers());
test('map notifications can be dismissed and automatically disappear after fifteen seconds',async()=>{
 jest.useFakeTimers();render(<MapDocumentPage/>);await screen.findByDisplayValue('Участок');
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Сохранить карту'}));});
 expect(screen.getByRole('status')).toBeInTheDocument();act(()=>jest.advanceTimersByTime(14999));expect(screen.getByRole('status')).toBeInTheDocument();
 act(()=>jest.advanceTimersByTime(1));expect(screen.queryByRole('status')).toBeNull();
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Сохранить карту'}));});expect(screen.getByRole('status')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Закрыть уведомление'}));expect(screen.queryByRole('status')).toBeNull();
});
test('error notifications have the same dismiss control',async()=>{
 workspaceRequest.mockImplementation((path,method)=>method==='PATCH'?Promise.reject(new Error('Не удалось сохранить')):Promise.resolve({map:record}));
 render(<MapDocumentPage/>);await screen.findByDisplayValue('Участок');
 fireEvent.click(screen.getByRole('button',{name:'Сохранить название и описание'}));expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось сохранить');
 fireEvent.click(screen.getByRole('button',{name:'Закрыть уведомление'}));expect(screen.queryByRole('alert')).toBeNull();
});
