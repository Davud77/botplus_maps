import React from 'react';
import { TileLayer, LayersControl } from 'react-leaflet';

const TMSLayers = () => {
  return (
    <>
      <LayersControl.BaseLayer name="Google Satellite">
        <TileLayer url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Google Hybrid">
        <TileLayer url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Google Maps">
        <TileLayer url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}" />
      </LayersControl.BaseLayer>
      
      <LayersControl.BaseLayer name="ESRI Satellite">
        <TileLayer url="https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
      </LayersControl.BaseLayer>
      
    </>
  );
};

export default TMSLayers;
