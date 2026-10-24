import {create} from 'zustand';
export interface PanoramaSettings {
  mode:'auto'|'points'; pointZoom:number; detail:'fast'|'balanced'|'precise';
  color:string; weight:number; outlineColor:string; outlineWidth:number;
  pointColor:string; pointRadius:number;
}
export const defaultPanoramaSettings:PanoramaSettings={mode:'auto',pointZoom:18,detail:'balanced',color:'#19a9e5',weight:4,outlineColor:'#ffffff',outlineWidth:2,pointColor:'#2db7f5',pointRadius:5};
export const usePanoramaRuntime=create<{revision:number;jobId:string|null;message:string;refresh:()=>void;start:(id:string)=>void;progress:(message:string)=>void;finish:(message:string)=>void}>(set=>({
 revision:0,jobId:null,message:'',refresh:()=>set(s=>({revision:s.revision+1})),start:id=>set({jobId:id,message:'Перестроение поставлено в очередь.'}),progress:message=>set({message}),finish:message=>set(s=>({jobId:null,message,revision:s.revision+1}))
}));
