import React from 'react';

interface SelectionPanelProps {
  handleSelection: (selectionType: string) => void;
  closePanel: () => void;
}

const SelectionPanel: React.FC<SelectionPanelProps> = ({ 
  handleSelection, 
  closePanel 
}) => {
  return (
    <div className="layers-menu visible">
      <div className="layers-header">
        <h3 className="layers-title">Выберите панорамы</h3>
        <button className="close-button" onClick={closePanel}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="24px"
            viewBox="0 0 24 24"
            width="24px"
            fill="#fff"
          >
            <path d="M0 0h24v24H0V0z" fill="none" />
            <path d="M18.3 5.71a1 1 0 0 0-1.41 0L12 10.59 7.11 5.71a1 1 0 1 0-1.41 1.41L10.59 12l-4.89 4.88a1 1 0 1 0 1.41 1.41L12 13.41l4.88 4.89a1 1 0 0 0 1.41-1.41L13.41 12l4.89-4.88a1 1 0 0 0 0-1.41z" />
          </svg>
        </button>
      </div>
      <div className="layers-select">
        <h3 className="select-title">Выбрано панорам:</h3>
        <h3 className="select-numb">тут должно быть количество выделенных панорам</h3>
      </div>
      <div className="tag-share">
        <h3 className="select-title">Поделиться</h3>
        <h3 className="select-numb">тут должна быть кнопка скопировать в буфур и поле инпут для ввода тега</h3>
      </div>
      <div className="edit-itemsinfo">
        <h3 className="select-title">Редактировать</h3>
        <h3 className="select-numb">тут должна быть таблица с атрибутами выделенных панорам</h3>
      </div>
      <h3 className="select-numb">при клике на кнопку которая открыла эту панель еще должна быть возможность выбрать на карте участок прямоугольным выделением </h3>
      <div className="edit-itemsinfo">
        <h3 className="select-title">удалить</h3>
        <h3 className="select-numb">тут должна быть кнопка которая удалит панорамы массово с потверждением</h3>
      </div>
    </div>
  );
};

export default SelectionPanel;