import React from 'react';

interface BasePanelProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export const BasePanel: React.FC<BasePanelProps> = ({ title, onClose, children }) => {
  return (
    <div className="map-side-panel">
      <div className="panel-header">
        <h3 className="panel-title">{title}</h3>
        <button className="panel-close-btn" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#666">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
      </div>
      <div className="panel-content">
        {children}
      </div>
      
    </div>
  );
};