import React from 'react';
import { OrthoImageType } from './OrthoLayer';


interface OrthoPanelProps {
  onClose: () => void;
  orthoImages: OrthoImageType[];
  onOrthoSelect: (ortho: OrthoImageType) => void;
  selectedOrthos?: OrthoImageType[];
  fitToBounds: (ortho: OrthoImageType) => void;
}

const OrthoPanel: React.FC<OrthoPanelProps> = ({
  onClose,
  orthoImages,
  onOrthoSelect,
  selectedOrthos = [],
  fitToBounds,
}) => {
  return (
    <div className="ortho-panel">
      <div className="ortho-panel-header">
        <h3 className="ortho-panel-title">Ортофотопланы</h3>
        <button className="ortho-panel-close" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="ortho-panel-content">
        <h4 className="ortho-subtitle">Последние загрузки</h4>
        <div className="ortho-cards-grid">
          {orthoImages.map((ortho) => {
            const isSelected = selectedOrthos.some((o) => o.id === ortho.id);
            return (
              <div
                key={ortho.id}
                className={`ortho-card ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  onOrthoSelect(ortho);
                  fitToBounds(ortho);
                }}
              >
                <div className="ortho-card-image-wrapper">
                  <img
                    // Главное — убедитесь, что backend действительно отдает ortho.url
                    src={ortho.url}
                    alt={ortho.filename}
                    className="ortho-card-image"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = '/placeholder.jpg';
                    }}
                  />
                </div>
                <div className="ortho-card-info">
                  <h5 className="ortho-card-title">{ortho.filename}</h5>
                  {ortho.bounds && (
                    <p className="ortho-card-bounds">
                      W: {ortho.bounds.west.toFixed(4)}, S: {ortho.bounds.south.toFixed(4)}
                      <br />
                      E: {ortho.bounds.east.toFixed(4)}, N: {ortho.bounds.north.toFixed(4)}
                    </p>
                  )}
                </div>
                <div className="ortho-card-actions">
                  <label>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {
                        onOrthoSelect(ortho);
                        fitToBounds(ortho);
                      }}
                    />
                    {' '}Показать
                  </label>
                </div>
              </div>
            );
          })}

          {orthoImages.length === 0 && (
            <div style={{ color: '#ccc', marginTop: '1rem' }}>
              Список ортофотопланов пуст...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default OrthoPanel;