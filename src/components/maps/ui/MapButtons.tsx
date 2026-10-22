// src/components/maps/ui/MapButtons.tsx
import React from 'react';
import { useUIStore, PanelType } from '../hooks/useUIStore';

interface MapButtonsProps {
  onTogglePano: () => void;
  isPanoLoading?: boolean;
  showSettings?: boolean;
  readOnly?: boolean;
}

export const MapButtons: React.FC<MapButtonsProps> = ({onTogglePano,showSettings = false, readOnly = false}) => {
  const {activePanel,togglePanel}=useUIStore();
  const buttons: [PanelType,string,string][]=[['activeLayers','▱','Слои на карте'],['baseLayers','▧','Подложки'],['pano','◎','Панорамы'],['ortho','▦','Ортофотопланы'],['vector','◇','Векторные слои']];
  if (showSettings) buttons.push(['settings','⚙','Настройки карты']);
  return <div className="map-buttons-container">{buttons.filter(([panel])=>!readOnly || panel==='settings').map(([panel,icon,title])=><button key={panel} className={`layers-button bp-tool ${activePanel===panel?'active':''}`} aria-label={title} aria-pressed={activePanel===panel} title={title} onClick={()=>{if(panel==='pano')onTogglePano();togglePanel(panel);}}><span aria-hidden="true">{icon}</span><small>{title}</small></button>)}</div>;
};
