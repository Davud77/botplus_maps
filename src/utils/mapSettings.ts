import { create } from 'zustand';
import { workspaceRequest } from './workspaceApi';
export interface Basemap { id: string; name: string; url: string; attribution: string; scheme: 'xyz'|'tms'; max_zoom: number; builtin?: boolean; }
export interface CoordinateSystem { id: string; name: string; definition: string; builtin: boolean; }
export interface MapSettings { coordinate_systems: CoordinateSystem[]; basemaps: Basemap[]; defaults: { coordinate_system: string; basemap: string }; }
export const useSettings = create<{ data: MapSettings | null; load: () => Promise<MapSettings> }>((set) => ({ data: null, load: async () => {
  const data = await workspaceRequest<MapSettings>('/settings/map'); set({ data }); return data;
} }));
