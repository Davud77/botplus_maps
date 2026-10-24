import React, { useRef, useState } from 'react';
import { BasePanel } from './BasePanel';
import { LayerSettings } from './LayerSettings';
import { useLayerStyleStore } from '../../hooks/useLayerStyleStore';
import { useMapStore } from '../../hooks/useMapStore';
import { useVectorStore } from '../../hooks/useVectorStore';
import { focusLayer } from '../../hooks/focusLayer';
export function ActiveLayersPanel({onClose,onRemovePanos}: {onClose:()=>void;onRemovePanos:()=>void}) {
  const {layers,update,move,reorder}=useLayerStyleStore();
  const {orthoImages,baseDefinition,baseLayerId}=useMapStore();
  const {layerSources}=useVectorStore();
  const [editing,setEditing]=useState<string|null>(null);
  const [focusError,setFocusError]=useState('');
  const [focusing,setFocusing]=useState<string|null>(null);
  const suppressClick=useRef(false);
  const navigate=async(key:string,keyboard:boolean)=>{
    if(suppressClick.current && !keyboard){suppressClick.current=false;return;}
    suppressClick.current=false;
    setFocusError('');setFocusing(key);
    try{await focusLayer(key);}catch(error){setFocusError((error as Error).message);}
    finally{setFocusing(null);}
  };
  const dragging=useRef<{key:string;x:number;y:number;started:boolean}|null>(null);
  const dropRef=useRef<{key:string;after:boolean}|null>(null);
  const [dragKey,setDragKey]=useState<string|null>(null);
  const [drop,setDrop]=useState<{key:string;after:boolean}|null>(null);
  const info=(key:string)=>{
    if(key==='basemap')return {kind:'basemap' as const,name:baseDefinition?.name || baseLayerId};
    if(key==='panoramas')return {kind:'panoramas' as const,name:'Панорамы'};
    if(key.startsWith('ortho:')){const ortho=orthoImages.find(o=>o.id===+key.slice(6));return {kind:'ortho' as const,name:ortho?.display_name||ortho?.filename||`Ортофото ${key.slice(6)}`};}
    return {kind:'vector' as const,name:layerSources[key.slice(7)]?.tableName || key.slice(7)};
  };
  const selected=layers.find(item=>item.key===editing);
  const finishDrag=()=>{dragging.current=null;dropRef.current=null;setDragKey(null);setDrop(null);};
  function pointerMove(event:React.PointerEvent<HTMLDivElement>) {
    const source=dragging.current;
    if(!source)return;
    if(!source.started && Math.hypot(event.clientX-source.x,event.clientY-source.y)<5)return;
    if(!source.started)event.currentTarget.setPointerCapture(event.pointerId);
    source.started=true;setDragKey(source.key);
    const row=document.elementFromPoint(event.clientX,event.clientY)?.closest<HTMLElement>('[data-layer-key]');
    const target=row?.dataset.layerKey;
    const next=row && target && target!==source.key ? {key:target,after:event.clientY>row.getBoundingClientRect().top+row.getBoundingClientRect().height/2} : null;
    dropRef.current=next;setDrop(next);
    const scroll=event.currentTarget.closest<HTMLElement>('.panel-content');
    if(scroll){const rect=scroll.getBoundingClientRect();if(event.clientY>rect.bottom-30)scroll.scrollTop+=12;else if(event.clientY<rect.top+30)scroll.scrollTop-=12;}
  }
  function remove(key:string) {
    if(key==='basemap') useMapStore.setState({baseLayerId:'none',baseLayerUrl:'',baseDefinition:null});
    else if(key==='panoramas') onRemovePanos();
    else if(key.startsWith('ortho:')) useMapStore.setState(s=>({selectedOrthoIds:s.selectedOrthoIds.filter(id=>id!==+key.slice(6))}));
    else useVectorStore.setState(s=>({activeVectorIds:new Set([...s.activeVectorIds].filter(id=>id!==key.slice(7)))}));
  }
  return <BasePanel title={selected?'Настройки слоя':'Слои на карте'} onClose={onClose}>
    {selected ? <LayerSettings layer={selected} {...info(selected.key)} onBack={()=>setEditing(null)} /> : <>
      <p className="bp-muted">Нажмите название, чтобы перейти к слою. Перетащите за название или маркер слева, чтобы изменить порядок.</p>
      {focusing && <p role="status">Определяем границы слоя…</p>}
      {focusError && <p role="alert">{focusError}</p>}
      {!layers.length && <p>Добавьте данные или выберите подложку.</p>}
      <div className="bp-sortable-layers" role="list" aria-label="Порядок слоёв карты">
        {layers.map(item=>{
          const {name,kind}=info(item.key);
          return <div key={item.key} role="listitem" data-layer-key={item.key}
            className={`bp-sortable-layer ${dragKey===item.key?'is-dragging':''} ${drop?.key===item.key ? (drop.after?'drop-after':'drop-before'):''}`}
            onPointerDown={event=>{
              if(event.button!==0)return;
              const control=(event.target as HTMLElement).closest('input,button,select,a');
              if(control && !control.classList.contains('bp-drag-handle') && !control.classList.contains('bp-layer-focus'))return;
              suppressClick.current=false;
              event.preventDefault();
              dragging.current={key:item.key,x:event.clientX,y:event.clientY,started:false};
            }}
            onPointerMove={pointerMove}
            onPointerUp={event=>{
              suppressClick.current=!!dragging.current?.started;
              if(dragging.current?.started && dropRef.current)reorder(dragging.current.key,dropRef.current.key,dropRef.current.after);
              if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
              finishDrag();
            }}
            onPointerCancel={finishDrag} onLostPointerCapture={finishDrag}>
            <button className="bp-drag-handle" aria-label={`Переместить ${name}`} title="Перетащить; с клавиатуры — стрелки вверх/вниз" onKeyDown={event=>{if(event.key==='ArrowUp'||event.key==='ArrowDown'){event.preventDefault();move(item.key,event.key==='ArrowUp'?-1:1);}}}>⠿</button>
            <input type="checkbox" checked={item.visible!==false} aria-label={`Видимость ${name}`} onChange={event=>update(item.key,{visible:event.target.checked})} />
            <button type="button" className="bp-sortable-name bp-layer-focus" title={`Показать ${name} на карте`} aria-label={`Перейти к слою ${name}`} onClick={event=>navigate(item.key,event.detail===0)}><strong>{name}</strong><small>{kind==='basemap'?'Подложка':kind==='ortho'?'Ортофотоплан':kind==='panoramas'?'Панорамы':'Векторный слой'}</small></button>
            <button className="bp-icon-button" aria-label={`Настройки ${name}`} title="Настройки слоя" onClick={()=>setEditing(item.key)}>⚙</button>
            <button className="bp-icon-button" aria-label={`Удалить ${name} с карты`} title="Удалить с карты" onClick={()=>remove(item.key)}>×</button>
          </div>;
        })}
      </div>
    </>}
  </BasePanel>;
}
