import React from 'react';
import '@testing-library/jest-dom';
import {render,screen,act} from '@testing-library/react';
import RasterTileLayer,{RasterLoadingStatus} from './RasterTileLayer';
let mockProps;
jest.mock('react-leaflet',()=>({TileLayer:props=>{mockProps=props;return null;}}));
test('512 px tiles preserve native detail and report the measured load, including errors',()=>{
 const view=render(<><RasterTileLayer telemetryKey="test" label="ОФП" url="/tile"/><RasterLoadingStatus/></>);
 expect(mockProps.tileSize).toBe(512);expect(mockProps.zoomOffset).toBe(-1);expect(mockProps.minNativeZoom).toBe(1);expect(mockProps.updateWhenZooming).toBe(false);
 act(()=>mockProps.eventHandlers.loading());expect(screen.getByRole('status')).toHaveTextContent('Загрузка…');
 act(()=>{mockProps.eventHandlers.tileload();mockProps.eventHandlers.load();});expect(screen.getByRole('status')).toHaveTextContent(/\d+\.\d{2} с/);
 act(()=>{mockProps.eventHandlers.loading();mockProps.eventHandlers.tileerror();mockProps.eventHandlers.load();});expect(screen.getByRole('status')).toHaveTextContent('Ошибок тайлов: 1');
 view.unmount();expect(screen.queryByRole('status')).toBeNull();
});
