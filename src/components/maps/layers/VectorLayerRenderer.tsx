import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useVectorStore } from '../hooks/useVectorStore';
import VectorTileLayer from './VectorTileLayer';

// Вспомогательная функция (оставляем как fallback)
const stringToColor = (str: string) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const c = (hash & 0x00ffffff).toString(16).toUpperCase();
  return '#' + '00000'.substring(0, 6 - c.length) + c;
};

export const VectorLayerRenderer = () => {
  const { activeVectorIds } = useVectorStore();
  
  // Хранилище стилей: { [tableName]: { style object } }
  const [dbStyles, setDbStyles] = useState<Record<string, any>>({});
  
  // Используем Ref для отслеживания текущих запросов, чтобы не запрашивать один слой дважды
  const fetchingRef = useRef<Set<string>>(new Set());

  // 1. ЗАГРУЗКА СТИЛЕЙ
  useEffect(() => {
    if (!activeVectorIds || activeVectorIds.size === 0) return;

    activeVectorIds.forEach(async (layerId) => {
      // ПРАВИЛЬНЫЙ ПАРСИНГ: "db-schema-table-name-with-dashes"
      // parts[0] = db, parts[1] = schema, остальное = tableName
      const parts = layerId.split('-');
      if (parts.length < 3) return;

      const dbName = parts[0];
      const schema = parts[1];
      const tableName = parts.slice(2).join('-'); // Собираем имя таблицы обратно

      // Если стиль уже есть или он прямо сейчас загружается — выходим
      if (dbStyles[tableName] || fetchingRef.current.has(layerId)) return;

      fetchingRef.current.add(layerId);

      try {
        const response = await fetch(`/api/vector/styles/${dbName}/${schema}/${tableName}`);
        
        if (response.ok) {
          const styleData = await response.json();
          setDbStyles((prev) => ({
            ...prev,
            [tableName]: {
              color: styleData.color,
              weight: styleData.weight || 1,
              opacity: 1,
              fillColor: styleData.fillColor || styleData.color,
              fill: true,
              fillOpacity: styleData.fillOpacity || 0.4,
            }
          }));
        } else {
          // Если стиля в БД нет (404), генерируем цвет по названию
          console.warn(`[Style] Using fallback for: ${tableName}`);
          const color = stringToColor(tableName);
          setDbStyles((prev) => ({
            ...prev,
            [tableName]: {
              color,
              weight: 1,
              opacity: 1,
              fillColor: color,
              fill: true,
              fillOpacity: 0.4,
            }
          }));
        }
      } catch (err) {
        console.error(`[Style] Fetch error for ${tableName}:`, err);
      } finally {
        // Убираем из списка загрузки (не удаляем из dbStyles, чтобы не качать повторно)
        fetchingRef.current.delete(layerId);
      }
    });
  }, [activeVectorIds]); // Убрали dbStyles из зависимостей, чтобы избежать циклов

  // 2. ГРУППИРОВКА СЛОЕВ ДЛЯ КОМБИНИРОВАННЫХ ТАЙЛОВ
  const groupedLayers = useMemo(() => {
    const groups: Record<string, string[]> = {};

    if (!activeVectorIds) return groups;

    activeVectorIds.forEach((layerId) => {
      const parts = layerId.split('-');
      if (parts.length < 3) return;

      const dbName = parts[0];
      const schema = parts[1];
      const tableName = parts.slice(2).join('-');

      const groupKey = `${dbName}/${schema}`;

      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push(tableName);
    });

    return groups;
  }, [activeVectorIds]);

  if (!activeVectorIds || activeVectorIds.size === 0) {
    return null;
  }

  return (
    <>
      {Object.entries(groupedLayers).map(([groupKey, tableNames]) => {
        const [dbName, schema] = groupKey.split('/');
        
        if (!tableNames.length) return null;

        const layersParam = tableNames.join(',');
        const tileUrl = `/api/vector/tiles/combined/${dbName}/{z}/{x}/{y}.pbf?layers=${layersParam}&schema=${schema}`;

        // Сборка финального объекта стилей для конкретной группы на карте
        const currentGroupStyles: Record<string, any> = {};
        
        tableNames.forEach((tableName) => {
          // Если данные из БД еще не пришли, показываем временный серый стиль
          currentGroupStyles[tableName] = dbStyles[tableName] || {
            weight: 1,
            color: '#888888',
            opacity: 0.5,
            fill: false
          };
        });

        return (
          <VectorTileLayer
            key={`${groupKey}-${layersParam}`} 
            url={tileUrl}
            styles={currentGroupStyles}
            active={true}
          />
        );
      })}
    </>
  );
};

export default VectorLayerRenderer;