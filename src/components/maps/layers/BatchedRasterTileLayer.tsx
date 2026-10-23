import {createElementObject,createTileLayerComponent,updateGridLayer,withPane} from '@react-leaflet/core';
import {TileLayerProps} from 'react-leaflet';
import {BatchRasterLayer} from './BatchRasterLayer';

export default createTileLayerComponent<BatchRasterLayer,TileLayerProps>(
  ({url,...options},context)=>createElementObject(new BatchRasterLayer(url,withPane(options,context)),context),
  (layer,props,previous)=>{updateGridLayer(layer,props,previous);if(props.url!==previous.url)layer.setUrl(props.url);},
);
