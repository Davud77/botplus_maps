// src/components/maps/ui/MapButtons.tsx
import React from 'react';
import { useUIStore, PanelType } from '../hooks/useUIStore';

interface MapButtonsProps {
  onTogglePano: () => void;
  isPanoLoading?: boolean;
}

export const MapButtons: React.FC<MapButtonsProps> = () => {
  const {activePanel,togglePanel}=useUIStore();
  const buttons: [PanelType,string,string][]=[['activeLayers','▱','Слои на карте'],['baseLayers','▧','Подложки'],['pano','◎','Панорамы'],['ortho','▦','Ортофотопланы'],['vector','◇','Векторные слои']];
  return <div className="map-buttons-container">{buttons.map(([panel,icon,title])=><button key={panel} className={`layers-button bp-tool ${activePanel===panel?'active':''}`} aria-label={title} title={title} onClick={()=>togglePanel(panel)}><span aria-hidden="true">{icon}</span><small>{title}</small></button>)}</div>;
};
