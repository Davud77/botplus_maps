import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import ProfileVector from './ProfileVector';
import {workspaceRequest} from '../../utils/workspaceApi';
import {fetchVectorDbs,fetchVectorLayers,createVectorLayer} from '../../utils/api';
let mockRole='admin';
jest.mock('../../hooks/useAuth',()=>({useAuth:()=>({user:{role:mockRole}})}));
jest.mock('../../utils/api',()=>({fetchVectorDbs:jest.fn(),fetchVectorLayers:jest.fn(),createVectorDb:jest.fn(),createVectorLayer:jest.fn()}));
jest.mock('../../utils/workspaceApi',()=>({workspaceRequest:jest.fn()}));
beforeEach(()=>{jest.clearAllMocks();mockRole='admin';workspaceRequest.mockResolvedValue({schemas:[{name:'public',can_delete:false},{name:'survey',can_delete:true}]});fetchVectorDbs.mockResolvedValue([{id:'one',name:'geodata',type:'internal',status:'connected'}]);fetchVectorLayers.mockResolvedValue([{id:1,schema:'public',tableName:'roads',geometryType:'LINESTRING',srid:4326,featureCount:250}]);createVectorLayer.mockResolvedValue({});});
test('inline layer form creates the chosen geometry in the selected database',async()=>{render(<ProfileVector/>);await screen.findByText('roads');fireEvent.click(screen.getByRole('button',{name:'Создать слой'}));fireEvent.change(screen.getByLabelText('Название таблицы'),{target:{value:'survey_points'}});fireEvent.change(screen.getByLabelText('Геометрия'),{target:{value:'POLYGON'}});fireEvent.click(screen.getByRole('button',{name:'Создать',exact:true}));await waitFor(()=>expect(createVectorLayer).toHaveBeenCalledWith('geodata','survey_points','POLYGON','public'));expect(await screen.findByText('Слой создан.')).toBeInTheDocument();});
test('viewer can inspect schemas but cannot create databases or layers',async()=>{mockRole='viewer';render(<ProfileVector/>);await screen.findByText('roads');expect(screen.queryByRole('button',{name:'Создать базу'})).toBeNull();expect(screen.queryByRole('button',{name:'Создать слой'})).toBeNull();});

test('schema form creates a named schema and exposes deletion for custom schemas',async()=>{
 render(<ProfileVector/>);await screen.findByText('roads');fireEvent.click(screen.getByRole('button',{name:'Создать схему'}));fireEvent.change(screen.getByLabelText('Название схемы'),{target:{value:'field_data'}});fireEvent.click(screen.getByRole('button',{name:'Создать',exact:true}));
 await waitFor(()=>expect(workspaceRequest).toHaveBeenCalledWith('/vector/schemas/geodata','POST',{name:'field_data'}));expect(await screen.findByText('Схема создана.')).toBeInTheDocument();expect(screen.getByRole('button',{name:'Удалить схему'})).toBeInTheDocument();
});
