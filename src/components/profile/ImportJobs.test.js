import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ImportJobs from './ImportJobs';
import { workspaceRequest } from '../../utils/workspaceApi';
const mockLoad=jest.fn();
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
jest.mock('../../utils/mapSettings',()=>({useSettings:()=>({data:{coordinate_systems:[{id:'EPSG:4326',name:'WGS 84'}]},load:mockLoad})}));
beforeEach(()=>{mockLoad.mockResolvedValue({});});
test('server-local import submits only a source reference and shows the durable job',async()=>{
  const job={id:'12345678-job',title:'Survey',root_id:'local',key:'survey/huge.tif',status:'queued',attempts:0,progress:0,message:'В очереди',result:null};
  let queued=false;
  workspaceRequest.mockImplementation((path,method)=>{
    if(path==='/imports/sources')return Promise.resolve({sources:[{id:'local',name:'local'}],upload_limit_bytes:2*1024**3});
    if(method==='POST'){queued=true;return Promise.resolve({job});}
    return Promise.resolve({jobs:queued?[job]:[]});
  });
  render(<ImportJobs />);
  await screen.findByRole('option',{name:'local'});
  fireEvent.change(screen.getByLabelText('Путь внутри папки'),{target:{value:'survey/huge.tif'}});
  fireEvent.change(screen.getByLabelText('Название слоя'),{target:{value:'Survey'}});
  fireEvent.click(screen.getByRole('button',{name:'Начать импорт'}));
  await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/imports/jobs','POST',{root_id:'local',key:'survey/huge.tif',title:'Survey',source_crs_id:null}));
  await screen.findByText('Можно закрыть страницу — обработка продолжится на сервере.',{exact:false});
  expect(await screen.findByText('Survey')).toBeTruthy();
});
test('failed jobs can be retried without reuploading their file',async()=>{
  const job={id:'failed-job',title:'Retry survey',root_id:'local',key:'ready.tif',status:'failed',attempts:1,progress:5,message:'Проверка не завершена',error:'Файл недоступен',result:null};
  workspaceRequest.mockImplementation(path=>Promise.resolve(path==='/imports/sources'?{sources:[],upload_limit_bytes:1024**3}:path.endsWith('/retry')?{status:'ok'}:{jobs:[job]}));
  render(<ImportJobs />);
  fireEvent.click(await screen.findByRole('button',{name:'Повторить'}));
  await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/imports/jobs/failed-job/retry','POST',{}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Повторить'}).disabled).toBe(false));
});
