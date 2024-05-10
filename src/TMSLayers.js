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
      <LayersControl.BaseLayer name="Yandex Satellite">
        <TileLayer url="https://sat01.maps.yandex.net/tiles?l=sat&v=3.675.0&x={x}&y={y}&z={z}&lang=ru_RU" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Yandex Maps">
        <TileLayer url="https://vec01.maps.yandex.net/tiles?l=map&v=4.89.0&x={x}&y={y}&z={z}&lang=ru_RU" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="ESRI Hybrid">
        <TileLayer url="https://server.arcgisonline.com/arcgis/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="ESRI Satellite">
        <TileLayer url="https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Yandex Hybrid">
        <TileLayer url="https://core-renderer-tiles.maps.yandex.net/tiles?l=skl&x={x}&y={y}&z={z}&scale=1&lang=en_US" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Bing Maps">
        <TileLayer url="http://ecn.t0.tiles.virtualearth.net/tiles/r{q}?g=1180&mkt=en-us&lbl=l1&stl=h&shading=hill&n=z" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Bing Satellite">
        <TileLayer url="http://ecn.t0.tiles.virtualearth.net/tiles/a{q}.jpeg?g=0" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="2Gis">
        <TileLayer url="http://tile.maps.2gis.com/tiles?v=1.3&x={x}&y={y}&z={z}" />
      </LayersControl.BaseLayer>
      {/* Добавляем TMS подложки здесь */}
      <LayersControl.BaseLayer name="TMS Layer 1">
        <TileLayer url="http://{s}.domain.com/{z}/{x}/{y}.png" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="TMS Layer 2">
        <TileLayer url="http://{s}.domain.com/{z}/{x}/{y}.png" />
      </LayersControl.BaseLayer>
      {/* Добавьте другие TMS слои здесь */}
    </>
  );
};

export default TMSLayers;
