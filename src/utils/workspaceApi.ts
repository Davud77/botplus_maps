import { API_BASE } from './api';
export type Role = 'admin' | 'editor' | 'viewer';
export const roleNames: Record<Role, string> = { admin: 'Администратор', editor: 'Редактор', viewer: 'Наблюдатель' };
export interface WorkspaceUser { id: number; username: string; role: Role; is_active: boolean; created_at: string; }
export interface VectorSource { dbName: string; schema: string; tableName: string; }
export interface LayerPresentation { key: string; visible?: boolean; opacity?: number; style?: { color?: string; weight?: number; fillOpacity?: number; radius?: number }; }
export function legacyBasemap(id: string): string { return (baseLayers as Record<string,string>)[id] || ''; }
export interface MapConfig {
  view: { center: [number, number]; zoom: number }; base_layer: string;
  coordinate_system?: string; base_layer_definition?: import('./mapSettings').Basemap | null;
  layer_settings?: LayerPresentation[];
  orthophoto_ids: number[]; vector_layers: VectorSource[]; show_panoramas: boolean;
}
export interface MapDocument {
  id: string; title: string; description: string; config: MapConfig; owner_id: number; owner_name?: string;
  revision: number; can_edit: boolean; published: boolean; public_slug: string | null; updated_at: string;
}
export async function workspaceRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    method, credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || data.error || `Ошибка сервера (${response.status})`);
  return data;
}
export const baseLayers = {
  light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  osm: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', none: '',
  google_hybrid: 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
  google_satellite: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
  google_maps: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
  esri_satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  esri_streets: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  esri_topo: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
  voyager: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  positron: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  topo: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
  cycle: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png',
  wikimedia: 'https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png',
};
