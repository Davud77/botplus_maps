import L from 'leaflet';

interface Frame {x:number;y:number;data?:string;error?:number;}
interface TileRequest {coords:L.Coords;image:HTMLImageElement;done:L.DoneCallback;cancelled:boolean;group?:Group;objectUrl?:string;}
interface Group {controller:AbortController;entries:TileRequest[];}

// Keep Leaflet's grid, bounds, native zoom, pan/zoom retention and layer ordering.
// Only the transport changes: visible tiles share progressive HTTP responses.
export class BatchRasterLayer extends L.TileLayer {
  private pending:TileRequest[]=[];
  private scheduled=false;
  private groups=new Set<Group>();
  private entries=new WeakMap<HTMLImageElement,TileRequest>();
  private active=true;
  private rasterUrl:string;

  constructor(url:string,options?:L.TileLayerOptions){
    super(url,options);this.rasterUrl=url;
    this.on('tileunload',event=>{
      const entry=this.entries.get((event as L.TileEvent).tile as HTMLImageElement);
      if(!entry)return;
      entry.cancelled=true;
      if(entry.objectUrl)URL.revokeObjectURL(entry.objectUrl);
      if(entry.group?.entries.every(item=>item.cancelled))entry.group.controller.abort();
    });
  }
  setUrl(url:string,noRedraw?:boolean):this{this.rasterUrl=url;return super.setUrl(url,noRedraw);}
  onAdd(map:L.Map):this{this.active=true;return super.onAdd(map);}
  onRemove(map:L.Map):this{
    this.active=false;
    this.scheduled=false;this.pending=[];
    this.groups.forEach(group=>group.controller.abort());this.groups.clear();
    return super.onRemove(map);
  }
  createTile(coords:L.Coords,done:L.DoneCallback):HTMLElement{
    const image=document.createElement('img');image.alt='';image.setAttribute('role','presentation');image.decoding='async';
    const entry:TileRequest={coords,image,done,cancelled:false};this.entries.set(image,entry);
    image.onload=()=>{if(entry.objectUrl)URL.revokeObjectURL(entry.objectUrl);if(!entry.cancelled)done(undefined,image);};
    image.onerror=()=>{if(entry.objectUrl)URL.revokeObjectURL(entry.objectUrl);if(!entry.cancelled)done(new Error('Не удалось загрузить тайл'),image);};
    this.pending.push(entry);
    if(!this.scheduled){this.scheduled=true;queueMicrotask(()=>this.flush());}
    return image;
  }
  private flush(){
    this.scheduled=false;
    const pending=this.pending.filter(entry=>!entry.cancelled);this.pending=[];
    if(!this.active)return;
    const byZoom=new Map<number,TileRequest[]>();
    pending.forEach(entry=>{const list=byZoom.get(entry.coords.z)||[];list.push(entry);byZoom.set(entry.coords.z,list);});
    byZoom.forEach(entries=>{for(let i=0;i<entries.length;i+=24)this.request(entries.slice(i,i+24));});
  }
  private async request(entries:TileRequest[]){
    const group:Group={controller:new AbortController(),entries};this.groups.add(group);
    entries.forEach(entry=>{entry.group=group;});
    const remaining=new Map<string,TileRequest[]>();
    entries.forEach(entry=>{const key=`${entry.coords.x},${entry.coords.y}`;remaining.set(key,[...(remaining.get(key)||[]),entry]);});
    const accept=(line:string)=>{
      if(!line.trim())return;
      const frame:Frame=JSON.parse(line);const key=`${frame.x},${frame.y}`;const targets=remaining.get(key);
      if(!targets)return;
      if(frame.error||!frame.data){remaining.delete(key);targets.forEach(entry=>{if(!entry.cancelled&&this.active)entry.done(new Error(`Тайл недоступен: ${frame.error||502}`),entry.image);});return;}
      const raw=atob(frame.data);const bytes=new Uint8Array(raw.length);
      for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
      remaining.delete(key);
      targets.forEach(entry=>{if(!entry.cancelled&&this.active){entry.objectUrl=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));entry.image.src=entry.objectUrl;}});
    };
    try{
      const endpoint=this.rasterUrl.replace('/{z}/{x}/{y}@2x.webp','/batch');
      const query=new URLSearchParams({z:String(entries[0].coords.z+(this.options.zoomOffset??0)),tiles:entries.map(entry=>`${entry.coords.x},${entry.coords.y}`).join(';')});
      const response=await fetch(`${endpoint}?${query}`,{credentials:'include',signal:group.controller.signal});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      if(!response.body){(await response.text()).split('\n').forEach(accept);}
      else{
        const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';let finished=false;
        try{
          while(true){
            const {done,value}=await reader.read();
            buffer+=decoder.decode(value,{stream:!done});
            if(buffer.length>8*1024*1024)throw new Error('Слишком большой тайл');
            let end:number;
            while((end=buffer.indexOf('\n'))>=0){accept(buffer.slice(0,end));buffer=buffer.slice(end+1);}
            if(done){if(buffer.trim())accept(buffer);finished=true;break;}
          }
        }finally{if(!finished)await reader.cancel().catch(()=>{});reader.releaseLock();}
      }
    }catch(error){
      // Report remaining visible tiles below. Cancelled batches have no callbacks.
    }finally{
      this.groups.delete(group);
      entries.forEach(entry=>{entry.group=undefined;});
      remaining.forEach(targets=>targets.forEach(entry=>{if(!entry.cancelled&&this.active)entry.done(new Error('Не удалось получить тайл'),entry.image);}));
    }
  }
}
