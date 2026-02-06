import React from 'react';
import Search from './Search';
import { MapButtons } from './MapButtons';

interface MapHeaderProps {
  onSearch: (query: string) => void;
  onTogglePano: () => void;
  isPanoLoading: boolean;
}

export const MapHeader: React.FC<MapHeaderProps> = ({ onSearch, onTogglePano, isPanoLoading }) => {
  return (
    <header className="map-header">
      <div className="first-box">
        <div className="logo">
          <a href="/">
            <img src="/images/logowhite2.png" alt="Logo" className="logo-image" />
          </a>
        </div>
        <div className="search-bar">
          <Search handleSearch={onSearch} />
        </div>
      </div>
      
      <div className="end-box">
        <div className="map-buttons-wrapper">
           <MapButtons onTogglePano={onTogglePano} isPanoLoading={isPanoLoading} />
        </div>
      </div>
    </header>
  );
};