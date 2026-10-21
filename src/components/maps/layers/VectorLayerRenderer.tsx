import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useVectorStore } from '../hooks/useVectorStore';
import VectorTileLayer from './VectorTileLayer';

// Вспомогательная функция (оставляем как fallback для генерации цвета)
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
  
  // [ИЗМЕНЕНО] Хранилище КОНФИГУРАЦИЙ стилей: 
  // { [layerId]: { type: 'single' | 'categorized', style?: ..., rules?: ... } }
  const [styleConfigs, setStyleConfigs] = useState<Record<string, any>>({});
  
  // Используем Ref для отслеживания текущих запросов
  const fetchingRef = useRef<Set<string>>(new Set());

  // 1. ЗАГРУЗКА СТИЛЕЙ
  useEffect(() => {
    if (!activeVectorIds || activeVectorIds.size === 0) return;

    activeVectorIds.forEach(async (layerId) => {
      // ПАРСИНГ ID: "db-schema-table-name-with-dashes"
      const parts = layerId.split('-');
      if (parts.length < 3) return;

      const dbName = parts[0];
      const schema = parts[1];
      const tableName = parts.slice(2).join('-'); 

      // Если конфиг уже есть или грузится — выходим
      if (styleConfigs[layerId] || fetchingRef.current.has(layerId)) return;

      fetchingRef.current.add(layerId);

      try {
        const response = await fetch(`/api/vector/styles/${dbName}/${schema}/${tableName}`);
        
        if (response.ok) {
          const configData = await response.json();
          
          // [ИЗМЕНЕНО] Сохраняем конфигурацию целиком, как прислал бэкенд
          setStyleConfigs((prev) => ({
            ...prev,
            [layerId]: configData
          }));
        } else {
          // [ИЗМЕНЕНО] Если стиля нет (404), генерируем дефолтный конфиг "single"
          console.warn(`[Style] Using fallback for: ${tableName}`);
          const color = stringToColor(tableName);
          
          setStyleConfigs((prev) => ({
            ...prev,
            [layerId]: {
              type: 'single', // Важно указать тип
              style: {
                color,
                weight: 1,
                opacity: 1,
                fillColor: color,
                fill: true,
                fillOpacity: 0.4,
              }
            }
          }));
        }
      } catch (err) {
        console.error(`[Style] Fetch error for ${tableName}:`, err);
      } finally {
        fetchingRef.current.delete(layerId);
      }
    });
  }, [activeVectorIds, styleConfigs]);

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

    Object.values(groups).forEach((tables) => tables.sort());
    return groups;
  }, [activeVectorIds]);

  const renderGroups = useMemo(() => Object.entries(groupedLayers).map(([groupKey, tableNames]) => {
    const [dbName, schema] = groupKey.split('/');
    const layersParam = tableNames.join(',');
    const configs: Record<string, any> = {};
    tableNames.forEach((tableName) => {
      configs[tableName] = styleConfigs[`${dbName}-${schema}-${tableName}`] || {
        type: 'single', style: { weight: 1, color: '#888888', opacity: 0.5, fill: false },
      };
    });
    return { key: `${groupKey}-${layersParam}`, configs,
      url: `/api/vector/tiles/combined/${encodeURIComponent(dbName)}/{z}/{x}/{y}.pbf?layers=${encodeURIComponent(layersParam)}&schema=${encodeURIComponent(schema)}` };
  }), [groupedLayers, styleConfigs]);

  return (
    <>
      {renderGroups.map((group) => (
        <VectorTileLayer key={group.key} url={group.url} styleConfigs={group.configs} active={true} />
      ))}
    </>
  );
};

export default VectorLayerRenderer;
