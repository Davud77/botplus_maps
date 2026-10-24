import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import ProfileOrthophotos from './ProfileOrthophotos';
import {workspaceRequest} from '../../utils/workspaceApi';
import {fetchOrthophotos, reprojectOrtho, updateOrtho} from '../../utils/api';
jest.mock('react-router-dom',()=>({Link:({to,...props})=>require('react').createElement('a',{href:to,...props})}),{virtual:true});
jest.mock('../../utils/api',()=>({fetchOrthophotos:jest.fn(),reprojectOrtho:jest.fn(),updateOrtho:jest.fn()}));
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
jest.mock('../../utils/mapSettings',()=>{const state={data:{coordinate_systems:[{id:'EPSG:3857',name:'Web Mercator',definition:'EPSG:3857'},{id:'EPSG:4326',name:'WGS 84',definition:'EPSG:4326'}]},load:()=>Promise.resolve()};return {useSettings:selector=>selector(state)};});
beforeEach(()=>{fetchOrthophotos.mockResolvedValue(Array.from({length:51},(_,i)=>({id:i+1,filename:`ortho-${i+1}.tif`,crs:'custom:stable',crs_name:'МСК Дагестан',bounds:null,is_visible:false})));});
test('catalog shows fifty rows per page and sends selected work to the background',async()=>{
 reprojectOrtho.mockResolvedValue({task_id:'new-job'});render(<ProfileOrthophotos/>);
 await screen.findByText('ortho-1.tif');expect(screen.queryByRole('button',{name:'Создать превью'})).toBeNull();expect(screen.getAllByRole('row')).toHaveLength(51);
 expect(screen.queryByText('ortho-51.tif')).toBeNull();expect(screen.getAllByText('МСК Дагестан')).toHaveLength(50);expect(screen.queryByText('custom:stable')).toBeNull();expect(screen.queryByText(/Системные логи/)).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Далее'}));expect(screen.getByText('ortho-51.tif')).toBeInTheDocument();expect(screen.getAllByRole('row')).toHaveLength(2);
 fireEvent.click(screen.getAllByRole('checkbox')[0]);expect(screen.queryByRole('button',{name:'Обновить'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Редактировать'}));fireEvent.click(screen.getByRole('button',{name:'Сменить проекцию'}));
 fireEvent.change(screen.getByLabelText('Целевая проекция'),{target:{value:'EPSG:4326'}});
 fireEvent.click(screen.getByRole('button',{name:'Создать задание'}));
 await waitFor(()=>expect(reprojectOrtho).toHaveBeenCalledWith(51,'EPSG:4326'));
 expect(await screen.findByRole('status')).toHaveTextContent('В очередь добавлено заданий: 1');
 expect(screen.getByRole('button',{name:'Редактировать'})).toBeEnabled();expect(screen.queryByRole('button',{name:'В EPSG:3857'})).toBeNull();
});

test('upload stays in the toolbar and rename changes the label without changing the source filename',async()=>{
 updateOrtho.mockResolvedValue({status:'success'});render(<ProfileOrthophotos/>);
 await screen.findByText('ortho-1.tif');
 expect(screen.getByRole('link',{name:'Загрузить ортофотопланы'}).closest('.ortho-header-actions')).toBeTruthy();
 fireEvent.click(screen.getAllByRole('checkbox')[1]);
 fireEvent.click(screen.getByRole('button',{name:'Редактировать'}));
 fireEvent.click(screen.getByRole('button',{name:'Переименовать'}));
 fireEvent.change(screen.getByLabelText('Название ортофотоплана'),{target:{value:'План участка'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить название'}));
 await waitFor(()=>expect(updateOrtho).toHaveBeenCalledWith(1,{display_name:'План участка'}));
 expect(await screen.findByText('План участка')).toBeInTheDocument();
 expect(screen.getByText('ortho-1.tif')).toBeInTheDocument();
});

test('COG is a single browser preparation action and works even for existing COG originals',async()=>{
 workspaceRequest.mockResolvedValue({job:{id:'prepared'}});render(<ProfileOrthophotos/>);await screen.findByText('ortho-1.tif');
 fireEvent.click(screen.getAllByRole('checkbox')[1]);fireEvent.click(screen.getByRole('button',{name:'Редактировать'}));
 expect(screen.queryByRole('button',{name:'Ускорить для карты'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'В формат COG'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/raster-display/orthophotos/1','POST',{}));
});
