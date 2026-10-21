import { create } from 'zustand';
import { LayerPresentation } from '../../../utils/workspaceApi';
interface LayerState { layers: LayerPresentation[]; sync: (keys: string[]) => void; update: (key:string, value: Partial<LayerPresentation>) => void; move: (key:string, delta:number) => void; }
export const useLayerStyleStore = create<LayerState>((set) => ({ layers: [],
  sync: keys => set(state => ({layers:[...keys.filter(key => !state.layers.some(item => item.key === key)).map(key => ({key,visible:true,opacity:1})),...state.layers.filter(item => keys.includes(item.key))]})),
  update: (key,value) => set(state => ({layers:state.layers.map(item => item.key === key ? {...item,...value,key} : item)})),
  move: (key,delta) => set(state => { const layers=[...state.layers]; const from=layers.findIndex(item => item.key === key); const to=from+delta; if(from<0 || to<0 || to>=layers.length) return state; [layers[from],layers[to]]=[layers[to],layers[from]]; return {layers}; }),
}));
