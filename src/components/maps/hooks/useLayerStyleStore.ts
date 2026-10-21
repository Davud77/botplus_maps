import { create } from 'zustand';
import { LayerPresentation } from '../../../utils/workspaceApi';
interface LayerState { layers: LayerPresentation[]; sync: (keys: string[]) => void; update: (key:string, value: Partial<LayerPresentation>) => void; move: (key:string, delta:number) => void; reorder: (key:string,target:string,after:boolean) => void; }
export const useLayerStyleStore = create<LayerState>((set) => ({ layers: [],
  sync: keys => set(state => {
    const added=keys.filter(key=>!state.layers.some(item=>item.key===key)).map(key=>({key,visible:true,opacity:1}));
    return {layers:[...added.filter(item=>item.key!=='basemap'),...state.layers.filter(item=>keys.includes(item.key)),...added.filter(item=>item.key==='basemap')]};
  }),
  update: (key,value) => set(state => ({layers:state.layers.map(item => item.key === key ? {...item,...value,key} : item)})),
  reorder: (key,target,after) => set(state => {
    if(key===target || !state.layers.some(item=>item.key===key) || !state.layers.some(item=>item.key===target)) return state;
    const item=state.layers.find(layer=>layer.key===key)!;
    const layers=state.layers.filter(layer=>layer.key!==key);
    layers.splice(layers.findIndex(layer=>layer.key===target)+(after?1:0),0,item);
    return {layers};
  }),
  move: (key,delta) => set(state => { const layers=[...state.layers]; const from=layers.findIndex(item => item.key === key); const to=from+delta; if(from<0 || to<0 || to>=layers.length) return state; [layers[from],layers[to]]=[layers[to],layers[from]]; return {layers}; }),
}));
