import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import TasksPanel from './TasksPanel';
import {workspaceRequest} from '../../utils/workspaceApi';
import {addOperationLog} from '../../utils/operationLogs';
let mockRole='admin';
jest.mock('../../hooks/useAuth',()=>({useAuth:()=>({user:{role:mockRole}})}));
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
const jobs=[{kind:'import',id:'done',title:'Готовый слой',status:'succeeded',progress:100,message:'Готово'},
 {kind:'media',id:'next',title:'Панорамы',status:'queued',progress:null,message:'Ожидание'},
 {kind:'display',id:'active',title:'Подготовка карты',status:'running',progress:35,message:'Обработка'}];
beforeEach(()=>{mockRole='admin';sessionStorage.clear();workspaceRequest.mockReset();workspaceRequest.mockImplementation(path=>Promise.resolve(path==='/system/logs'?{events:[{at:'2026-10-22T10:00:00Z',service:'import',message:'Исходник зарегистрирован'}],services:[]}:{jobs}));});
test('one list orders running, queued and finished jobs and dismisses finished cards',async()=>{
 render(<TasksPanel/>);await screen.findByText('Готовый слой');
 expect(screen.getAllByRole('article').map(e=>e.querySelector('strong').textContent)).toEqual(['Подготовка карты','Панорамы','Готовый слой']);
 expect(screen.getByRole('progressbar',{name:'Прогресс Подготовка карты'})).toHaveAttribute('value','35');
 expect(screen.queryByText('Подключённые оригиналы')).toBeNull();expect(screen.queryByRole('button',{name:'Обновить задания'})).toBeNull();
 expect(workspaceRequest.mock.calls.some(([,m])=>m==='POST')).toBe(false);
 workspaceRequest.mockImplementation(path=>Promise.resolve({jobs:jobs.filter(j=>j.id!=='done')}));
 fireEvent.click(screen.getByRole('button',{name:'Готово'}));
 await waitFor(()=>expect(screen.queryByText('Готовый слой')).toBeNull());
 expect(workspaceRequest).toHaveBeenCalledWith('/tasks/import/done/done','POST',{});
});
test('logs combine the orthophoto journal with server events',async()=>{
 addOperationLog('Список успешно обновлен. Загружено файлов: 11');render(<TasksPanel/>);
 fireEvent.click(screen.getByRole('tab',{name:'Логи'}));
 expect(await screen.findByText('Исходник зарегистрирован')).toBeInTheDocument();
 expect(screen.getByRole('log')).toHaveTextContent('Загружено файлов: 11');
});
test('editors can read local logs without requesting administrator logs',async()=>{
 mockRole='editor';render(<TasksPanel/>);fireEvent.click(screen.getByRole('tab',{name:'Логи'}));
 expect(await screen.findByRole('log')).toBeInTheDocument();expect(workspaceRequest.mock.calls.some(([p])=>p==='/system/logs')).toBe(false);
});
test('cancel uses the correct endpoint for the common card',async()=>{
 render(<TasksPanel/>);await screen.findByText('Подготовка карты');
 fireEvent.click(screen.getAllByRole('button',{name:'Отменить'})[0]);
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/raster-display/jobs/active/cancel','POST',{}));
});
