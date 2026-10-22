import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import {MapButtons} from './MapButtons';
const mockToggle=jest.fn();
jest.mock('../hooks/useUIStore',()=>({useUIStore:()=>({activePanel:null,togglePanel:mockToggle})}));
test('opening panoramas activates the map layer as well as its panel',()=>{const activate=jest.fn();render(<MapButtons onTogglePano={activate}/>);fireEvent.click(screen.getByRole('button',{name:'Панорамы'}));expect(activate).toHaveBeenCalledTimes(1);expect(mockToggle).toHaveBeenCalledWith('pano');});
