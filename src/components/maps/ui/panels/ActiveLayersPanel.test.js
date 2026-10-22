import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ActiveLayersPanel } from './ActiveLayersPanel';
import { useMapStore } from '../../hooks/useMapStore';
import { useLayerStyleStore } from '../../hooks/useLayerStyleStore';
import { focusLayer } from '../../hooks/focusLayer';
jest.mock('../../hooks/focusLayer', () => ({focusLayer:jest.fn(async()=>{})}));
beforeEach(()=>{
  jest.clearAllMocks();
  window.PointerEvent=MouseEvent;
  HTMLElement.prototype.setPointerCapture=jest.fn();
  HTMLElement.prototype.hasPointerCapture=()=>false;
  useMapStore.setState({orthoImages:[{id:7,filename:'Участок 7'},{id:8,filename:'Участок 8'}]});
  useLayerStyleStore.setState({layers:[{key:'ortho:7'},{key:'ortho:8'}]});
});
test('clicking an accessible layer name focuses the layer',()=>{
  render(<ActiveLayersPanel onClose={()=>{}} onRemovePanos={()=>{}} />);
  fireEvent.click(screen.getByRole('button',{name:'Перейти к слою Участок 7'}));
  expect(focusLayer).toHaveBeenCalledWith('ortho:7');
});
test('dragging a layer name changes order without centering the map',()=>{
  const original=document.elementFromPoint;
  const view=render(<ActiveLayersPanel onClose={()=>{}} onRemovePanos={()=>{}} />);
  const name=screen.getByRole('button',{name:'Перейти к слою Участок 7'});
  const row=name.closest('[data-layer-key]');
  const target=view.container.querySelector('[data-layer-key="ortho:8"]');
  document.elementFromPoint=()=>target;
  try{
    fireEvent.pointerDown(name,{button:0,clientX:10,clientY:10});
    expect(row.setPointerCapture).not.toHaveBeenCalled();
    fireEvent.pointerMove(row,{clientX:20,clientY:40});
    expect(row.setPointerCapture).toHaveBeenCalledTimes(1);
    fireEvent.pointerUp(row);
    fireEvent.click(name);
    expect(useLayerStyleStore.getState().layers.map(x=>x.key)).toEqual(['ortho:8','ortho:7']);
    expect(focusLayer).not.toHaveBeenCalled();
  }finally{document.elementFromPoint=original;}
});
