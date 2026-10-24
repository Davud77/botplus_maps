import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import '@testing-library/jest-dom';
import {LayerSettings} from './LayerSettings';
import {useLayerStyleStore} from '../../hooks/useLayerStyleStore';
import {usePanoramaRuntime} from '../../../../utils/panoramaSettings';
import {workspaceRequest} from '../../../../utils/workspaceApi';
const mockLoad=jest.fn(async()=>{});
jest.mock('../../../../utils/mapSettings',()=>({useSettings:()=>({data:{coordinate_systems:[{id:'EPSG:4326',name:'WGS 84'}]},load:mockLoad})}));
jest.mock('../../../../utils/workspaceApi',()=>({workspaceRequest:jest.fn(async()=>({job:{id:'rebuild-job'}}))}));
beforeEach(()=>{mockLoad.mockResolvedValue();workspaceRequest.mockResolvedValue({job:{id:'rebuild-job'}});useLayerStyleStore.setState({layers:[{key:'panoramas'}]});usePanoramaRuntime.setState({jobId:null,message:'',revision:0});jest.clearAllMocks();});
function Settings(){const layer=useLayerStyleStore(s=>s.layers[0]);return <LayerSettings layer={layer} kind="panoramas" name="Панорамы" onBack={()=>{}}/>;}
test('panorama settings persist as layer presentation and rebuild enters background queue',async()=>{
 render(<Settings/>);
 fireEvent.change(screen.getByLabelText('Цвет линии'),{target:{value:'#123456'}});
 fireEvent.change(screen.getByLabelText('Уровень появления точек'),{target:{value:'20'}});
 expect(useLayerStyleStore.getState().layers[0].panorama).toEqual(expect.objectContaining({color:'#123456',pointZoom:20}));
 fireEvent.click(screen.getByRole('button',{name:'Обновить видимую область'}));expect(usePanoramaRuntime.getState().revision).toBe(1);
 fireEvent.click(screen.getByRole('button',{name:'Перестроить покрытие'}));
 await waitFor(()=>expect(usePanoramaRuntime.getState().jobId).toBe('rebuild-job'));
 expect(workspaceRequest).toHaveBeenCalledWith('/media/coverage/rebuild','POST',{});
 expect(screen.getByRole('button',{name:'Перестроить покрытие'})).toBeDisabled();
});
