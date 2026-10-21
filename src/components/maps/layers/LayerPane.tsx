import React, { useEffect } from 'react';
import { Pane, useMap } from 'react-leaflet';
interface Props { name:string; style: {zIndex:number;opacity:number}; children:React.ReactNode; }
// React Leaflet's Pane only applies its style at creation. Update the existing
// element explicitly so sliders and reordering never recreate tile sources.
function PaneAppearance({name,style}: Omit<Props,'children'>) {
  const map=useMap();
  useEffect(()=>{const pane=map.getPane(name); if(pane) {pane.style.zIndex=String(style.zIndex);pane.style.opacity=String(style.opacity);} },[map,name,style.zIndex,style.opacity]);
  return null;
}
export function LayerPane({name,style,children}:Props) {
  return <Pane name={name} style={style}><PaneAppearance name={name} style={style} />{children}</Pane>;
}
