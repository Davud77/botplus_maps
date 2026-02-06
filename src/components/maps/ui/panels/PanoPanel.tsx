// src/components/maps/ui/panels/PanoPanel.tsx
import React from 'react';
import { BasePanel } from './BasePanel';

export const PanoPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  return (
    <BasePanel title="Панорамы" onClose={onClose}>
      <div style={{ padding: '10px', color: '#666', fontSize: '13px' }}>
        Выберите точку на карте, чтобы просмотреть панораму.
      </div>
      {/* Здесь можно добавить список последних просмотренных или фильтры */}
    </BasePanel>
  );
};