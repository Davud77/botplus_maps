import React, { useRef, useEffect, useState } from 'react';
// @ts-ignore
import Marzipano from 'marzipano';
import './MediaViewer.css';

interface PanoramaViewerProps {
  markerId: string;
  endpoint?: string;
  isExpanded: boolean;
  onDataLoad?: (data: { title: string; date: string; alt: string }) => void;
}
type Mode = 'photo' | 'panorama';
interface Asset {
  url: string;
  info: { filename: string; display_name?: string; width: number; height: number; media_type: Mode; direction?: number };
}

const PanoramaViewer: React.FC<PanoramaViewerProps> = ({ markerId, isExpanded, onDataLoad, endpoint }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const viewerInstanceRef = useRef<any>(null);
  const onDataLoadRef = useRef(onDataLoad);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [mode, setMode] = useState<Mode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { onDataLoadRef.current = onDataLoad; }, [onDataLoad]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let url: string | null = null;
    setAsset(null); setMode(null); setZoom(1); setError(null);
    const load = async () => {
      try {
        const response = await fetch(endpoint || `/api/pano_info/${markerId}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`Не удалось получить сведения: ${response.status}`);
        const info = await response.json();
        if (!active) return;
        onDataLoadRef.current?.({ title: info.display_name || info.filename || 'Фотография',
          date: info.timestamp || info.upload_date || 'Дата не указана', alt: Number(info.altitude || 0).toFixed(1) });
        const image = await fetch(endpoint ? `${endpoint}/image` : `/api/pano_info/${markerId}/download`, { signal: controller.signal });
        if (!image.ok) throw new Error(`Не удалось загрузить изображение: ${image.status}`);
        const blob = await image.blob();
        if (!active) return;
        url = URL.createObjectURL(blob);
        // Compatibility with older API responses: decode only this selected image.
        if (!info.width || !info.height) {
          const size = await new Promise<{ width: number; height: number }>((resolve, reject) => {
            const probe = new Image();
            probe.onload = () => resolve({ width: probe.naturalWidth, height: probe.naturalHeight });
            probe.onerror = () => reject(new Error('Не удалось прочитать изображение'));
            probe.src = url!;
          });
          Object.assign(info, size);
        }
        if (!active) return;
        info.media_type = info.media_type || (info.width >= 1024 && info.width === info.height * 2 ? 'panorama' : 'photo');
        setAsset({ url, info });
      } catch (error: any) {
        if (active && error.name !== 'AbortError') setError(error.message || 'Не удалось открыть изображение');
      }
    };
    load();
    return () => {
      active = false; controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [markerId,endpoint]);

  const selectedMode = mode || asset?.info.media_type || 'photo';
  useEffect(() => {
    const element = viewerRef.current;
    if (!asset || !element) return;
    element.replaceChildren();
    setError(null);
    let viewer: any = null;
    let observer: ResizeObserver | null = null;
    try {
      if (selectedMode === 'photo') {
        const image = document.createElement('img');
        image.src = asset.url;
        image.alt = asset.info.display_name || asset.info.filename;
        image.className = 'bp-photo-image';
        image.draggable = false;
        image.style.width = `${zoom * 100}%`;
        image.style.height = `${zoom * 100}%`;
        element.appendChild(image);
      } else {
        viewer = new Marzipano.Viewer(element, { stage: { progressive: true }, controls: { mouseViewMode: 'drag' } });
        const geometry = new Marzipano.EquirectGeometry([{ width: asset.info.width }]);
        const limiter = Marzipano.RectilinearView.limit.traditional(asset.info.width, 120 * Math.PI / 180);
        const view = new Marzipano.RectilinearView({ yaw: Number(asset.info.direction || 0) * Math.PI / 180,
          pitch: 0, roll: 0, fov: Math.PI / 4 }, limiter);
        const scene = viewer.createScene({ source: Marzipano.ImageUrlSource.fromString(asset.url), geometry, view,
          pinFirstLevel: true });
        scene.layer().textureStore().addEventListener('textureError', (_tile: any, error: Error) => {
          setError(error?.message || 'Не удалось загрузить панораму. Откройте режим «Фото».');
        });
        scene.switchTo({ transitionDuration: 0 });
        viewerInstanceRef.current = viewer;
        if (typeof ResizeObserver !== 'undefined') {
          observer = new ResizeObserver(() => viewer.updateSize());
          observer.observe(element);
        }
      }
    } catch (error: any) {
      setError(error.message || 'Не удалось открыть изображение');
    }
    return () => {
      observer?.disconnect(); viewer?.destroy();
      viewerInstanceRef.current = null;
      element.replaceChildren();
    };
  }, [asset, selectedMode, zoom]);
  useEffect(() => { viewerInstanceRef.current?.updateSize(); }, [isExpanded]);

  return <div className="panorama-container">
    {asset && <div className="bp-media-tools" role="group" aria-label="Просмотр изображения">
      <button type="button" aria-pressed={selectedMode === 'photo'} onClick={() => { setMode('photo'); setZoom(1); }}>Фото</button>
      <button type="button" aria-pressed={selectedMode === 'panorama'} disabled={asset.info.width !== asset.info.height * 2}
        onClick={() => setMode('panorama')}>360°</button>
      {selectedMode === 'photo' && <>
        <button type="button" aria-label="Уменьшить фото" disabled={zoom <= 1} onClick={() => setZoom(value => Math.max(1, value - 0.5))}>−</button>
        <button type="button" aria-label="Увеличить фото" disabled={zoom >= 4} onClick={() => setZoom(value => Math.min(4, value + 0.5))}>＋</button>
      </>}
    </div>}
    {!asset && !error && <div className="bp-media-loading" role="status">Загрузка изображения…</div>}
    {error && <div className="pano-error-overlay" role="alert">{error}</div>}
    <div ref={viewerRef} className={`panorama-viewer ${selectedMode === 'photo' ? 'bp-photo-viewer' : ''}`} />
  </div>;
};
export default PanoramaViewer;
