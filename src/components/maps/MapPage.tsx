import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker } from 'react-leaflet';

import 'leaflet/dist/leaflet.css';
import L, { Map as LeafletMap } from 'leaflet';

import PanoramaViewer from './panoLayer/PanoramaViewer';
import Search from './Search';
import BaseLayer from './baseLayer/BaseLayer';
import {
  ContextMenu,
  MapEventHandlers,
  handleCopyCoordinates,
} from './ContextMenu';
import { defaultIcon, activeIcon } from '../icons';
import PanoLayer from './panoLayer/PanoLayer';
import PanoLayerButton from './panoLayer/PanoLayerButton';
import OrthoLayer, { OrthoImageType } from './orthoLayer/OrthoLayer';
import OrthoPanel from './orthoLayer/OrthoPanel';
import SelectionPanel from './panoLayer/SelectionPanel';
import CustomZoomControl from './CustomZoomControl';
import ProfileNav from '../ProfileNav';

// Тип для маркеров панорам
interface MarkerType {
  id: string;
  lat: number;
  lng: number;
}

const MapPage: React.FC = () => {
  // id выбранного маркера (строка или null)
  const [selectedMarker, setSelectedMarker] = useState<string | null>(null);
  // Раскрыт ли блок панорамы на весь экран
  const [isExpanded, setIsExpanded] = useState(false);
  // Виден ли блок панорамы внизу
  const [isVisible, setIsVisible] = useState(false);

  // Список маркеров, загруженных из PanoLayer
  const [markers, setMarkers] = useState<MarkerType[]>([]);

  // Начальный центр карты
  const [mapCenter, setMapCenter] = useState<[number, number]>([43, 47]);

  // Состояние контекстного меню
  const [contextMenu, setContextMenu] = useState({
    visible: false,
    x: 0,
    y: 0,
    lat: 0,
    lng: 0,
  });

  // Текущий базовый слой
  const [baseLayer, setBaseLayer] = useState<string>(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
  );

  // Отображать ли слой панорам
  const [showPanoLayer, setShowPanoLayer] = useState<boolean>(false);
  const [isLoadingMarkers, setIsLoadingMarkers] = useState<boolean>(false);

  // Ортофото
  const [orthoImages, setOrthoImages] = useState<OrthoImageType[]>([]);
  const [showOrthoPanel, setShowOrthoPanel] = useState<boolean>(false);
  const [showOrthoLayer, setShowOrthoLayer] = useState<boolean>(false);
  const [selectedOrthos, setSelectedOrthos] = useState<OrthoImageType[]>([]);

  // Показать ли кнопку "Добавить панораму"
  const [showAddPanoramaButton, setShowAddPanoramaButton] = useState<boolean>(false);

  // Панель массового выбора панорам
  const [showSelectionPanel, setShowSelectionPanel] = useState(false);

  // Ссылка на карту
  const mapRef = useRef<LeafletMap | null>(null);

  // Хендлер клика по маркеру панорамы
  const handleMarkerClick = useCallback(async (marker: MarkerType) => {
    try {
      // Можно дополнительно проверить, что такой маркер реально есть
      // Например, запросить краткую инфу
      const response = await fetch(`https://api.botplus.ru/pano_info/${marker.id}`);
      await response.json(); // не обязательно сохранять, если только нужна проверка

      // При успехе сохраняем id и показываем панораму
      setSelectedMarker(marker.id);
      setIsVisible(true);
    } catch (error) {
      console.error('Ошибка при запросе данных о маркере:', error);
      alert('Не удалось загрузить данные о панораме.');
    }
  }, []);

  // Раскрыть/свернуть панораму
  const toggleHeight = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Закрыть панораму
  const closeInfo = useCallback(() => {
    setIsVisible(false);
    setSelectedMarker(null);
  }, []);

  // Копирование координат
  const copyCoordinatesHandler = useCallback(() => {
    handleCopyCoordinates(contextMenu);
  }, [contextMenu]);

  // Сохраняем ссылку на карту
  const SetMapRef = () => {
    const map = useMap();
    useEffect(() => {
      mapRef.current = map;
    }, [map]);
    return null;
  };

  // Поиск по координатам
  const handleSearch = (searchInput: string) => {
    const coords = searchInput.split(',').map((c) => parseFloat(c.trim()));
    if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
      if (mapRef.current) {
        mapRef.current.setView(coords as [number, number], 18);
      }
      setMapCenter(coords as [number, number]);
    } else {
      alert('Неверный формат координат. Используйте "55.123, 47.456"');
    }
  };

  // Смена базового слоя
  const handleLayerChange = (layerUrl: string) => {
    setBaseLayer(layerUrl);
  };

  // Включение/выключение слоя панорам
  const handlePanoLayerToggle = () => {
    setShowPanoLayer(prev => !prev);
  };

  // Включение/выключение ортофото
  const handleToggleOrthoLayer = (images: OrthoImageType[]) => {
    setOrthoImages(images);
    // Открыть/закрыть боковую панель
    setShowOrthoPanel((prev) => !prev);
    // Сам слой
    setShowOrthoLayer((prev) => !prev);
  };

  // Выбор конкретного орто
  const handleOrthoSelect = (ortho: OrthoImageType) => {
    setSelectedOrthos((prevSelected) => {
      const alreadySelected = prevSelected.some((o) => o.id === ortho.id);
      if (alreadySelected) {
        return prevSelected.filter((o) => o.id !== ortho.id);
      }
      return [...prevSelected, ortho];
    });
  };

  // Фокус на bounds выбранного орто
  const fitToOrthoBounds = (ortho: OrthoImageType) => {
    if (!mapRef.current || !ortho.bounds) return;
    const sw = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.west, ortho.bounds.south));
    const ne = L.CRS.EPSG3857.unproject(L.point(ortho.bounds.east, ortho.bounds.north));
    mapRef.current.fitBounds(L.latLngBounds(sw, ne));
  };

  // Пример пустого обработчика
  const MapClickHandler = () => {
    useMapEvents({
      click: () => {
        // закрывать какие-то меню, если надо
      },
    });
    return null;
  };

  const handleAddPanoramaClick = () => {
    // Пример: просто переходим на страницу загрузки
    window.location.href = '/upload';
  };

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative' }}>
      {/* Шапка с логотипом, поиском и т.д. */}
      <header className="map-header">
        <div className="first-box">
          <div className="logo">
            <a href="/">
              <img
                src="/images/logowhite2.png"
                alt="Логотип"
                className="logo-image"
              />
            </a>
          </div>
          <div className="search-bar">
            <Search handleSearch={handleSearch} />
          </div>
        </div>
        <div className="end-box">


          {selectedMarker && isVisible ? (
            <>
              {/* Если панорама открыта, показываем кнопки управления (инфа, свернуть/закрыть) */}
              <div className="map-buttons">
                <button
                  className="button_control pointinfo"
                  onClick={() => console.log('Информация о точке')}
                >
                  <img
                    src="/images/svg/info-icon.svg"
                    alt="Информация"
                    width="30"
                    height="30"
                  />
                </button>
              </div>
              <div className="map-buttons">
                <div className="visible_control">
                  <button className="button_control" onClick={closeInfo}>
                    <img
                      src="/images/svg/close-icon.svg"
                      alt="Закрыть"
                      width="30"
                      height="30"
                    />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Если панорама не открыта, показываем другие кнопки */}
              {showAddPanoramaButton && (
                <div className="map-buttons">
                  <button
                    className="layers-button"
                    onClick={() => setShowSelectionPanel(!showSelectionPanel)}
                    title="Выбор"
                  >
                    <img
                      src="/images/svg/select-icon.svg"
                      alt="Выбор"
                      width="24"
                      height="24"
                    />
                  </button>

                  {showSelectionPanel && (
                    <SelectionPanel
                      handleSelection={(type: string) => {
                        console.log('Selected type:', type);
                        setShowSelectionPanel(false);
                      }}
                      closePanel={() => setShowSelectionPanel(false)}
                    />
                  )}

                  <button
                    className="layers-button"
                    onClick={handleAddPanoramaClick}
                    title="Добавить панорамы"
                  >
                    <img
                      src="/images/svg/add-pano-icon.svg"
                      alt="Добавить панорамы"
                      width="24"
                      height="24"
                    />
                  </button>
                </div>
              )}

              <div className="map-buttons">
                <BaseLayer handleLayerChange={handleLayerChange} />
                <PanoLayerButton 
                  handlePanoLayerToggle={handlePanoLayerToggle}
                  isLoading={isLoadingMarkers}
                />
                <button
                  className="layers-button"
                  onClick={() => handleToggleOrthoLayer(orthoImages)}
                  title="Показать ортофото"
                >
                  <img
                    src="/images/svg/ortho-icon.svg"
                    alt="Ортофото"
                    width="24"
                    height="24"
                    className="ortho-icon"
                  />
                </button>
              </div>

            </>
          )}
          <div className="map-buttons">
            <ProfileNav />
          </div>

        </div>
      </header>

      {/* Контейнер под панораму, если маркер выбран */}
      {selectedMarker && isVisible && (
        <div
          className="selected-marker-info"
          style={{ height: isExpanded ? '100%' : '50%' }}
        >
          {/* Передаём выбранный markerId (уже точно string) в панораму */}
          <PanoramaViewer
            markerId={selectedMarker}
            isExpanded={isExpanded}
          />
        </div>
      )}

      {/* Сама карта */}
      <MapContainer
        center={mapCenter}
        zoom={5}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        maxZoom={20}
      >
        <SetMapRef />

        <TileLayer url={baseLayer} maxZoom={20} />
        <CustomZoomControl />

        {showPanoLayer && (
          <PanoLayer
            selectedMarker={selectedMarker}
            onMarkerClick={handleMarkerClick}
          />
        )}

        {showOrthoLayer &&
          selectedOrthos.map((ortho) => (
            <TileLayer
              key={ortho.id}
              url={`https://api.botplus.ru/orthophotos/${ortho.id}/tiles/{z}/{x}/{y}.png`}
              maxZoom={20}
              opacity={0.7}
            />
          ))}

        <MapClickHandler />
        <MapEventHandlers setContextMenu={setContextMenu} />
      </MapContainer>

      {/* Панель с выбором ортофото */}
      {showOrthoPanel && (
        <OrthoPanel
          onClose={() => setShowOrthoPanel(false)}
          orthoImages={orthoImages}
          onOrthoSelect={handleOrthoSelect}
          selectedOrthos={selectedOrthos}
          fitToBounds={fitToOrthoBounds}
        />
      )}

      {/* Контекстное меню (копировать координаты) */}
      <ContextMenu
        contextMenu={contextMenu}
        handleCopyCoordinates={copyCoordinatesHandler}
      />
    </div>
  );
};

export default MapPage;
