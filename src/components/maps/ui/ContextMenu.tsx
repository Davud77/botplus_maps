// src/components/maps/ContextMenu.tsx

import React from 'react';
import { useMapEvents } from 'react-leaflet';

export interface ContextMenuProps {
  contextMenu: {
    visible: boolean;
    x: number;
    y: number;
    lat: number;
    lng: number;
  };
  handleCopyCoordinates: () => void;
}

export const ContextMenu: React.FC<ContextMenuProps> = ({ contextMenu, handleCopyCoordinates }) => {
  if (!contextMenu.visible) return null;

  return (
    <div style={{ position: 'absolute', top: contextMenu.y, left: contextMenu.x, zIndex: 1000 }}>
      <button onClick={handleCopyCoordinates}>Копировать координаты</button>
    </div>
  );
};

export const handleCopyCoordinates = (contextMenu: ContextMenuProps['contextMenu']) => {
  const coordinates = `${contextMenu.lat}, ${contextMenu.lng}`;
  navigator.clipboard.writeText(coordinates);
  alert(`Координаты скопированы: ${coordinates}`);
};

export const handleRightClick = (
  event: any,
  setContextMenu: React.Dispatch<React.SetStateAction<ContextMenuProps['contextMenu']>>
) => {
  event.originalEvent.preventDefault();
  const { latlng, containerPoint } = event;
  setContextMenu({
    visible: true,
    x: containerPoint.x,
    y: containerPoint.y,
    lat: latlng.lat,
    lng: latlng.lng,
  });
};

export const MapEventHandlers = ({
  setContextMenu,
}: {
  setContextMenu: React.Dispatch<React.SetStateAction<ContextMenuProps['contextMenu']>>;
}) => {
  useMapEvents({
    contextmenu: (event) => {
      handleRightClick(event, setContextMenu);
    },
    click: () => {
      setContextMenu((prev) => ({ ...prev, visible: false }));
    },
  });
  return null;
};

export default ContextMenu;