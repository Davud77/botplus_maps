import React from 'react';
import { BasePanel } from './BasePanel';

export const SelectionPanel: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  return (
    <BasePanel title="Инструменты" onClose={onClose}>
      <div className="tools-section">
        <h4>Выбор панорам</h4>
        <div className="tool-row">
          <span>Выбрано:</span> <strong>0</strong>
        </div>
        <button className="tool-btn danger">🗑 Удалить выбранные</button>
      </div>

      <div className="tools-section">
        <h4>Поделиться</h4>
        <div className="tool-row">
          <input type="text" placeholder="Введите тег..." className="tool-input" />
          <button className="tool-btn primary">Копировать</button>
        </div>
      </div>

      <div className="tools-section">
        <h4>Выделение</h4>
        <button className="tool-btn outline">⬜ Прямоугольное выделение</button>
      </div>

      <style>{`
        .tools-section { margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; }
        .tools-section h4 { margin: 0 0 10px 0; font-size: 14px; color: #555; }
        .tool-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 13px; }
        .tool-input { flex: 1; padding: 6px; border: 1px solid #ccc; border-radius: 4px; }
        .tool-btn { 
          width: 100%; padding: 8px; border: none; border-radius: 4px; 
          cursor: pointer; font-weight: 500; font-size: 13px; margin-bottom: 5px;
        }
        .tool-btn.primary { background: #2196F3; color: white; }
        .tool-btn.danger { background: #ffebee; color: #d32f2f; }
        .tool-btn.outline { background: white; border: 1px solid #ccc; color: #333; }
        .tool-btn:hover { opacity: 0.9; }
      `}</style>
    </BasePanel>
  );
};