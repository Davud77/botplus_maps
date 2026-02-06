import React from 'react';
import { useMapEvents } from 'react-leaflet';

interface MapEventsProps {
  setContextMenu: React.Dispatch<React.SetStateAction<{
    visible: boolean;
    x: number;
    y: number;
    lat: number;
    lng: number;
  }>>;
}

export const MapEvents: React.FC<MapEventsProps> = ({ setContextMenu }) => {
  useMapEvents({
    contextmenu: (event) => {
      event.originalEvent.preventDefault();
      const { latlng, containerPoint } = event;
      setContextMenu({
        visible: true,
        x: containerPoint.x,
        y: containerPoint.y,
        lat: latlng.lat,
        lng: latlng.lng,
      });
    },
    click: () => {
      setContextMenu((prev) => ({ ...prev, visible: false }));
    },
  });
  return null;
};