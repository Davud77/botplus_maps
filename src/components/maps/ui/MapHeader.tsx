import React, { useLayoutEffect, useRef } from 'react';
import Search from './Search';
import { MapButtons } from './MapButtons';

interface MapHeaderProps {
  showSettings?: boolean;
  readOnly?: boolean;
  onSearch: (query: string) => void;
  onTogglePano: () => void;
  isPanoLoading: boolean;
}

export const MapHeader: React.FC<MapHeaderProps> = ({ onSearch, onTogglePano, isPanoLoading, showSettings, readOnly }) => {
  const headerRef = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const header = headerRef.current;
    const wrapper = header?.closest<HTMLElement>('.map-page-wrapper');
    if (!header || !wrapper) return;
    const measure = () => wrapper.style.setProperty('--map-toolbar-height', `${header.getBoundingClientRect().height}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(header);
    return () => { observer.disconnect(); wrapper.style.removeProperty('--map-toolbar-height'); };
  }, []);
  return (
    <header className="map-header" ref={headerRef} aria-label="Инструменты карты">
      <div className="first-box">
        <div className="logo">
          <a href="/" aria-label="BotPlus Maps — все карты">B+</a>
        </div>
        <div className="search-bar">
          <Search handleSearch={onSearch} />
        </div>
      </div>

      <div className="end-box">
        <div className="map-buttons-wrapper">
           <MapButtons showSettings={showSettings} readOnly={readOnly} onTogglePano={onTogglePano} isPanoLoading={isPanoLoading} />
        </div>
      </div>
    </header>
  );
};