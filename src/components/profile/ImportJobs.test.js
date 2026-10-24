import '@testing-library/jest-dom';
import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import ImportJobs from './ImportJobs';
import {workspaceRequest} from '../../utils/workspaceApi';
jest.mock('react-router-dom',()=>({Link:({to,...p})=>require('react').createElement('a',{href:to,...p})}),{virtual:true});
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
beforeEach(()=>{workspaceRequest.mockImplementation(path=>Promise.resolve(path==='/imports/sources'?{sources:[{id:'nas',name:'NAS'}],upload_limit_bytes:2*1024**3}:path.startsWith('/imports/browse')?{entries:[{name:'survey.tif',key:'survey.tif',directory:false},{name:'panos',key:'panos',directory:true}],parent:null,next_offset:null}:{job:{id:'import-job',title:'survey.tif'}}));});
test('file upload is first and the NAS browser chooses a file without manual path entry',async()=>{
 render(<ImportJobs/>);
 expect(screen.getByRole('button',{name:'Загрузить файл'}).className).toBe('active');
 fireEvent.click(screen.getByRole('button',{name:'С диска / NAS'}));
 fireEvent.click(await screen.findByRole('button',{name:/survey.tif/}));
 fireEvent.click(screen.getByRole('button',{name:'Импортировать',exact:true}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/imports/register','POST',{root_id:'nas',key:'survey.tif',title:''}));
 expect(await screen.findByRole('status')).toHaveTextContent('В очередь добавлено заданий: 1');
 expect(workspaceRequest.mock.calls.some(([path])=>path==='/imports/jobs')).toBe(false);
 expect(screen.queryByLabelText('Путь внутри папки')).toBeNull();
});
test('NAS panorama folder submits only the reference with 360 filter and no processing request',async()=>{
 render(<ImportJobs/>);fireEvent.click(screen.getByRole('button',{name:/Панорамы JPEG/}));fireEvent.click(screen.getByRole('button',{name:'С диска / NAS'}));
 const choose=await screen.findByRole('button',{name:'Выбрать эту папку'});await waitFor(()=>expect(choose).toBeEnabled());fireEvent.click(choose);
 fireEvent.click(screen.getByRole('button',{name:'Начать импорт панорам'}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/media/imports','POST',{root_id:'nas',key:'.',only_360:true}));
});
test('a raster folder is submitted as one queued import',async()=>{
 render(<ImportJobs/>);fireEvent.click(screen.getByRole('button',{name:'С диска / NAS'}));
 const choose=await screen.findByRole('button',{name:'Выбрать эту папку'});await waitFor(()=>expect(choose).toBeEnabled());fireEvent.click(choose);
 fireEvent.click(screen.getByRole('button',{name:'Импортировать',exact:true}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/imports/register','POST',{root_id:'nas',key:'.',title:''}));
});
