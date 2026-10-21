// src/components/maps/ui/panels/PanoPanel.tsx
import React from 'react';
import { BasePanel } from './BasePanel';

// Описываем структуру данных, которые приходят от открытой панорамы
interface PanoPanelProps {
  onClose: () => void;
  added: boolean; onAdd: ()=>void;
  panoDetails?: {
    title: string;
    date: string;
    alt: string;
  } | null;
}

export const PanoPanel: React.FC<PanoPanelProps> = ({ onClose, panoDetails, added, onAdd }) => {
  return (
    <BasePanel title="Панорамы" onClose={onClose}><p className="bp-muted">Точки загружаются по области карты с серверной кластеризацией.</p><button className="ws-primary" disabled={added} onClick={onAdd}>{added ? '✓ Уже на карте' : '+ Добавить панорамы'}</button>
      <div className="panel-content" style={{ padding: '15px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        
        {panoDetails ? (
          // Если данные есть (панорама открыта) — показываем информацию о ней
          <>
            <h3 style={{ margin: 0, fontSize: '14px', wordBreak: 'break-all', color: 'var(--color-text)' }}>
              {panoDetails.title}
            </h3>
            <div style={{ color: 'var(--color-text-light)', fontSize: '12px' }}>
              {panoDetails.date}
            </div>
            <div style={{ color: 'var(--color-text)', fontSize: '13px', marginTop: '4px' }}>
              Alt: <strong>{panoDetails.alt} m</strong>
            </div>
          </>
        ) : (
          // Если данных нет (ничего не выбрано) — показываем стандартную заглушку
          <div style={{ color: '#666', fontSize: '13px' }}>
            Выберите точку на карте, чтобы просмотреть панораму.
          </div>
        )}

      </div>
    </BasePanel>
  );
};