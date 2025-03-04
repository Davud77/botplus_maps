// import { useEffect } from 'react';
// import { useMap } from 'react-leaflet';
// import GeoRasterLayer from 'georaster-layer-for-leaflet';
// import chroma from 'chroma-js';
// import parseGeoraster from 'georaster';


// const CogLayer = () => {
//   const map = useMap();

//   useEffect(() => {
//     const loadCog = async () => {
//       try {
//         const cogUrl = '/images/Gergebil_WGS84.tif';
        
//         // Загружаем и парсим GeoTIFF
//         const response = await fetch(cogUrl);
//         const arrayBuffer = await response.arrayBuffer();
//         const georaster = await parseGeoraster(arrayBuffer);

//         const options = {
//           resolution: 256,
//           debugLevel: 0,
//           pixelValuesToColorFn: (values: number[]) => {
//             const [red, green, blue] = values.slice(0, 3);
//             if (red === 0 && green === 0 && blue === 0) return null;
//             return chroma([red, green, blue]).hex();
//           },
//           georaster, // Передаем распарсенный георастр
//           useCors: true,
//         };

//         const layer = new (GeoRasterLayer as any)(options);
//         layer.addTo(map);

//         // Автоматическое определение границ
//         map.fitBounds(layer.getBounds());

//         return () => {
//           map.removeLayer(layer);
//         };
//       } catch (error) {
//         console.error('Error loading COG layer:', error);
//         alert('Failed to load COG layer. Check console for details.');
//       }
//     };

//     loadCog();
//   }, [map]);

//   return null;
// };

// export default CogLayer;

// CogLayer.tsx

// Отключил, чтобы не мешало
import { useEffect } from 'react';
import { useMap } from 'react-leaflet';


const CogLayer = () => {
  return null;
};

export default CogLayer;