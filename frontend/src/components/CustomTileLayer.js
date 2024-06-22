import React, { useEffect, useState } from 'react';
import { TileLayer } from 'react-leaflet';
import PouchDB from 'pouchdb-browser';

const db = new PouchDB('tilecache');

const cacheTile = async (url) => {
  try {
    const response = await fetch(url);
    const blob = await response.blob();
    await db.put({
      _id: url,
      data: blob,
      _attachments: {
        'tile.png': {
          content_type: 'image/png',
          data: blob
        }
      }
    });
  } catch (error) {
    console.error('Failed to cache tile:', error);
  }
};

const getCachedTile = async (url) => {
  try {
    const blob = await db.getAttachment(url, 'tile.png');
    return URL.createObjectURL(blob);
  } catch (error) {
    return url;
  }
};

const CustomTileLayer = ({ urlTemplate, ...props }) => {
  const [tiles, setTiles] = useState({});

  useEffect(() => {
    const cacheTiles = async () => {
      if (!urlTemplate) return; // Проверяем, что urlTemplate определен

      const tileUrls = [
        urlTemplate.replace('{z}', '15').replace('{x}', '0').replace('{y}', '0'),
        // Add more URLs as needed
      ];

      for (const tileUrl of tileUrls) {
        await cacheTile(tileUrl);
        const cachedUrl = await getCachedTile(tileUrl);
        setTiles(prevTiles => ({ ...prevTiles, [tileUrl]: cachedUrl }));
      }
    };

    cacheTiles();
  }, [urlTemplate]);

  return (
    <TileLayer
      url={(coords) => {
        if (!urlTemplate) return ''; // Проверяем, что urlTemplate определен

        const tileUrl = urlTemplate
          .replace('{z}', coords.z.toString())
          .replace('{x}', coords.x.toString())
          .replace('{y}', coords.y.toString());
        return tiles[tileUrl] || tileUrl;
      }}
      {...props}
    />
  );
};

export default CustomTileLayer;
