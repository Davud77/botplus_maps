import React, { useMemo } from 'react';
import { useVectorStore } from '../hooks/useVectorStore';
import VectorTileLayer from './VectorTileLayer';

// Вспомогательная функция для генерации уникального цвета по строке
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

  // 1. ГРУППИРОВКА СЛОЕВ
  // Мы не рендерим каждый слой отдельно. Мы группируем их по Базе и Схеме.
  // Результат: { "dbName/schema": ["table1", "table2", "table3"] }
  const groupedLayers = useMemo(() => {
    const groups: Record<string, string[]> = {};

    if (!activeVectorIds) return groups;

    activeVectorIds.forEach((layerId) => {
      // Парсинг ID: "dbName-schema-tableName"
      const parts = layerId.split('-');
      if (parts.length < 3) return;

      const dbName = parts[0];
      const schema = parts[1];
      // Собираем имя таблицы обратно (на случай дефисов в названии)
      const tableName = parts.slice(2).join('-');

      // Ключ группы
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
        
        // Если в группе нет таблиц, пропускаем
        if (!tableNames.length) return null;

        // 2. ФОРМИРОВАНИЕ ЕДИНОГО URL
        // Перечисляем все таблицы через запятую в параметре ?layers=...
        const layersParam = tableNames.join(',');
        
        // API endpoint, который мы создали в vector.py (get_combined_tiles)
        const tileUrl = `/api/vector/tiles/combined/${dbName}/{z}/{x}/{y}.pbf?layers=${layersParam}&schema=${schema}`;

        // 3. ПОДГОТОВКА СТИЛЕЙ
        // Формируем объект стилей для каждого слоя в этой группе
        const styles: Record<string, any> = {};
        
        tableNames.forEach((tableName) => {
          const color = stringToColor(tableName);
          // Ключ в объекте styles должен совпадать с именем слоя в PBF (имя таблицы)
          styles[tableName] = {
            weight: 1,
            color: color,
            opacity: 1,
            fillColor: color,
            fill: true,
            fillOpacity: 0.4,
          };
        });

        // 4. РЕНДЕРИНГ ОДНОГО КОМПОНЕНТА НА ВСЮ ГРУППУ
        // Это сокращает количество сетевых запросов в N раз (где N - количество слоев)
        return (
          <VectorTileLayer
            key={groupKey + '-' + layersParam} // Ключ меняется при добавлении/удалении слоев, заставляя перерисоваться
            url={tileUrl}
            styles={styles} // Передаем ВСЕ стили разом (убедитесь, что VectorTileLayer обновлен для приема styles)
            active={true}
          />
        );
      })}
    </>
  );
};

export default VectorLayerRenderer;