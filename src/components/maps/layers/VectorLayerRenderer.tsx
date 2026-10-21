import React, { useEffect, useMemo, useState } from 'react';
import { LayerPane } from './LayerPane';
import { useVectorStore } from '../hooks/useVectorStore';
import { useLayerStyleStore } from '../hooks/useLayerStyleStore';
import { LayerPresentation, VectorSource, workspaceRequest } from '../../../utils/workspaceApi';
import VectorTileLayer from './VectorTileLayer';
function StyledVector({source,presentation,pane}: {source:VectorSource;presentation:LayerPresentation;pane:string}) {
  const [sourceStyle,setSourceStyle]=useState<any>({type:'single',style:{color:'#20664e',weight:2,fillOpacity:0.25}});
  const path=[source.dbName,source.schema,source.tableName].map(encodeURIComponent).join('/');
  useEffect(()=>{let live=true; workspaceRequest(`/vector/styles/${path}`).then(style=>{if(live)setSourceStyle(style);}).catch(()=>{});return()=>{live=false;};},[path]);
  const configs=useMemo(()=>{
    const custom=presentation.style; const overridden=custom && Object.keys(custom).length>0;
    return {[source.tableName]: overridden ? {type:'single' as const,style:{...sourceStyle.style,...custom,fill:true,fillColor:custom.color || sourceStyle.style?.color || '#20664e'}} : sourceStyle};
  },[presentation.style,sourceStyle,source.tableName]);
  return <VectorTileLayer url={`/api/vector/tiles/${path}/{z}/{x}/{y}.pbf`} styleConfigs={configs} pane={pane} coordinateUrl={`/settings/coordinates?crs=${encodeURIComponent(presentation.coordinate_system||'EPSG:4326')}`} active />;
}
export const VectorLayerRenderer = () => {
  const {activeVectorIds,layerSources}=useVectorStore(); const {layers}=useLayerStyleStore();
  return <>{[...activeVectorIds].map(id=>{const presentation=layers.find(item=>item.key===`vector:${id}`);const source=layerSources[id]; if(!source || presentation?.visible===false)return null; const order=layers.findIndex(item=>item.key===`vector:${id}`); const pane=`vector-overlay-${encodeURIComponent(id)}`; return <LayerPane key={id} name={pane} style={{zIndex:400+layers.length-Math.max(order,0),opacity:presentation?.opacity??1}}><StyledVector source={source} presentation={presentation||{key:id}} pane={pane} /></LayerPane>;})}</>;
};
export default VectorLayerRenderer;
