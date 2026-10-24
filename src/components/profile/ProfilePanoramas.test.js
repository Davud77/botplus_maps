import '@testing-library/jest-dom';
import React from 'react';
import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import ProfilePanoramas from './ProfilePanoramas';
import {workspaceRequest} from '../../utils/workspaceApi';
let mockRole='admin';const mockFit=jest.fn();let mockItems;
jest.mock('../../hooks/useAuth',()=>({useAuth:()=>({user:{id:1,role:mockRole}})}));
jest.mock('react-router-dom',()=>({Link:({to,...p})=>require('react').createElement('a',{href:to,...p})}),{virtual:true});
jest.mock('react-leaflet',()=>({MapContainer:({children})=><div>{children}</div>,TileLayer:({url})=><div data-testid="basemap">{url}</div>,useMap:()=>({fitBounds:mockFit})}));
jest.mock('../maps/layers/PanoLayer',()=>({__esModule:true,default:({endpoint,query})=><div data-testid="markers">{endpoint}?{query}</div>}));
jest.mock('../maps/ui/viewers/PanoramaViewer',()=>()=>null);
jest.mock('../../utils/workspaceApi',()=>({baseLayers:{osm:'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'},workspaceRequest:jest.fn()}));
beforeEach(()=>{jest.clearAllMocks();localStorage.clear();mockRole='admin';jest.spyOn(window,'confirm').mockReturnValue(true);mockItems=[{id:1,name:'one.jpg',latitude:43,longitude:47,tags:''},{id:2,name:'two.jpg',latitude:43,longitude:47,tags:''}];workspaceRequest.mockImplementation((path,method,body)=>{if(method==='POST'){if(body.action==='trash')mockItems=mockItems.filter(i=>!body.ids.includes(i.id));return Promise.resolve({status:'ok',affected:body.ids?.length||0,active_total:mockItems.length,trash_total:2-mockItems.length});}return Promise.resolve(path==='/media/folders'?{folders:[{id:7,name:'Съёмка'}]}:path.startsWith('/media/bounds')?{bounds:null}:{items:mockItems,next_cursor:null,total:mockItems.length});});});
afterEach(()=>jest.restoreAllMocks());
test('delete uses reversible trash and deleted entries disappear from the list',async()=>{
 render(<ProfilePanoramas/>);fireEvent.click(await screen.findByLabelText('Выбрать one.jpg'));
 expect(screen.queryByRole('button',{name:'Снять выбор'})).toBeNull();expect(screen.queryByRole('button',{name:'Переместить'})).toBeNull();expect(screen.queryByLabelText('Папка назначения')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Удалить',exact:true}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/bulk','POST',{ids:[1],action:'trash'}));
 await waitFor(()=>expect(screen.queryByText('one.jpg')).toBeNull());expect(await screen.findByText('two.jpg')).toBeInTheDocument();expect(screen.getByRole('status')).toHaveTextContent('Удалено в корзину: 1. Осталось панорам: 1.');
});
test('trash has exactly three actions, supports permanent deletion and clearing',async()=>{
 render(<ProfilePanoramas/>);await screen.findByText('one.jpg');fireEvent.click(screen.getByRole('link',{name:'Корзина'}));
 const toolbar=await screen.findByRole('toolbar',{name:'Действия корзины'});expect(within(toolbar).getAllByRole('button').map(b=>b.textContent)).toEqual(['Удалить окончательно','Очистить','Восстановить']);
 fireEvent.click(await screen.findByLabelText('Выбрать one.jpg'));fireEvent.click(within(toolbar).getByRole('button',{name:'Удалить окончательно'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/bulk','POST',{ids:[1],action:'purge'}));
 await waitFor(()=>expect(within(toolbar).getByRole('button',{name:'Очистить'})).toBeEnabled());fireEvent.click(within(toolbar).getByRole('button',{name:'Очистить'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/trash/empty','POST',{}));
});
test('column visibility and order persist across mounts',async()=>{
 const view=render(<ProfilePanoramas/>);await screen.findByText('one.jpg');fireEvent.click(screen.getByRole('button',{name:'Настройка полей'}));
 const settings=screen.getByRole('region',{name:'Настройка полей'});fireEvent.click(within(settings).getByLabelText('Теги'));fireEvent.click(within(settings).getByRole('button',{name:'Выше: Название'}));
 expect(screen.queryByRole('columnheader',{name:'Теги'})).toBeNull();expect(screen.getAllByRole('columnheader')[1]).toHaveTextContent('Название');
 view.unmount();render(<ProfilePanoramas/>);await screen.findByText('one.jpg');expect(screen.queryByRole('columnheader',{name:'Теги'})).toBeNull();expect(screen.getAllByRole('columnheader')[1]).toHaveTextContent('Название');
});
test('map has OpenStreetMap tiles and bounded panorama markers',async()=>{
 render(<ProfilePanoramas/>);await screen.findByText('one.jpg');fireEvent.click(screen.getByRole('button',{name:'Карта',exact:true}));
 expect(screen.getByTestId('markers')).toHaveTextContent('/api/media/markers?trash=0');expect(screen.getByTestId('basemap')).toHaveTextContent('tile.openstreetmap.org');
});
test('viewer has no modification controls',async()=>{
 mockRole='viewer';render(<ProfilePanoramas/>);await screen.findByRole('button',{name:'Открыть one.jpg'});expect(screen.queryByRole('button',{name:'Удалить',exact:true})).toBeNull();expect(screen.queryByLabelText('Выбрать страницу')).toBeNull();
});
test('catalog requests 200 records and opens a floating viewer outside the table',async()=>{
 render(<ProfilePanoramas/>);fireEvent.click(await screen.findByRole('button',{name:'Открыть one.jpg'}));
 expect(workspaceRequest.mock.calls.some(([path])=>path==='/media/catalog?trash=0&limit=200&after=0')).toBe(true);
 const viewer=screen.getByRole('region',{name:'Просмотр панорамы'});expect(viewer.parentElement).toBe(document.body);expect(viewer).toHaveClass('ws-media-preview');
 fireEvent.click(screen.getByRole('button',{name:'Закрыть просмотр'}));expect(screen.queryByRole('region',{name:'Просмотр панорамы'})).toBeNull();
});
