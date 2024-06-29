import React from 'react';
import { useMapEvents } from 'react-leaflet';

const ContextMenu = ({ contextMenu, handleCopyCoordinates }) => {
  if (!contextMenu.visible) return null;

  return (
    <div className="context-menu" style={{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }}>
      <button onClick={handleCopyCoordinates} className="button_white">Скопировать координаты</button>
    </div>
  );
};

const MapEventHandlers = ({ setView }) => {
  useMapEvents({
    contextmenu: (event) => {
      const { latlng, containerPoint } = event;
      setView(latlng.lat, latlng.lng, containerPoint.x, containerPoint.y);
    },
    click: () => {
      setView(null, null, null, null);
    }
  });
  return null;
};

const handleRightClick = (setContextMenu) => (lat, lng, x, y) => {
  setContextMenu({
    visible: true,
    x: x,
    y: y,
    lat: lat,
    lng: lng
  });
};

const handleCopyCoordinates = (contextMenu, setContextMenu) => () => {
  if (contextMenu.lat != null && contextMenu.lng != null) {
    const coords = `${contextMenu.lat.toFixed(6)}, ${contextMenu.lng.toFixed(6)}`;
    navigator.clipboard.writeText(coords)
      .catch(err => console.error('Failed to copy coordinates:', err));
    setContextMenu({ ...contextMenu, visible: false });
  } else {
    console.error('Coordinates are null');
  }
};

export { ContextMenu, MapEventHandlers, handleRightClick, handleCopyCoordinates };
