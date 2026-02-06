// src/utils/api.ts

// Базовый путь. В PROD это будет относительный путь (nginx разрулит).
// В DEV это перехватит прокси и отправит на localhost:5000.
const API_BASE = "/api"; 

/* -------------------- Общие типы -------------------- */
export interface ApiOk {
  status: "ok";
  [k: string]: any;
}

export interface ApiError {
  status: "error" | "fail";
  message: string;
}

export type ApiResp = ApiOk | ApiError;

/* -------------------- Типы данных (Data Types) -------------------- */

// Панорамы
export interface PanoItem {
  id: number;
  filename: string;
  latitude?: number;
  longitude?: number;
  tags?: string;
  upload_date?: string;
}

// Ортофотопланы
export interface OrthoItem {
  id: number;
  filename: string;
  url: string;
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
}

// Векторные слои
export interface VectorLayerItem {
  id: number;
  schema: string;
  tableName: string;
  geometryType: string;
  featureCount: number;
  srid?: number;
}

export interface VectorDbItem {
  id: string;
  name: string;
  host: string;
  port: number;
  status: 'connected' | 'error';
  type: 'internal' | 'external';
  layers?: VectorLayerItem[];
}

// Bounding Box для запросов по области
export interface BBox {
  minLng: number;
  minLat: number;
  maxLng: number;
  maxLat: number;
}

/* -------------------- Низкоуровневые вызовы -------------------- */
async function apiGet<T = any>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    credentials: "include", // Важно для кук
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

async function apiPost<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

async function apiPut<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`PUT ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

async function apiDelete<T = any>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`DELETE ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

/* -------------------- Auth API -------------------- */
export type MeResponse =
  | { authenticated: false }
  | {
      authenticated: true;
      user: {
        id: number;
        username: string;
        exp: number;
        exp_unix: number;
        exp_human: string;
      };
    };

export async function authMe(): Promise<MeResponse> {
  return apiGet<MeResponse>("/auth/me");
}

export async function authLogin(username: string, password: string): Promise<ApiResp> {
  return apiPost<ApiResp>("/auth/login", { username, password });
}

export async function authLogout(): Promise<ApiResp> {
  return apiPost<ApiResp>("/auth/logout", {});
}

/* -------------------- Data API -------------------- */

// --- Панорамы ---
export async function fetchPanoramas<T = any>(): Promise<T> {
  return apiGet<T>("/panoramas");
}

export async function updatePanoTags(id: number, tags: string): Promise<ApiOk> {
  return apiPut<ApiOk>(`/pano_info/${id}`, { tags });
}

export async function deletePano(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/pano_info/${id}`);
}

export async function uploadFiles<T = any>(formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST /upload failed: ${res.status} ${text}`);
  }
  return res.json();
}

// --- Ортофото ---
export async function fetchOrthophotos(): Promise<OrthoItem[]> {
  return apiGet<OrthoItem[]>("/orthophotos");
}

export async function deleteOrtho(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/orthophotos/${id}`);
}

/* -------------------- Vector / PostGIS API -------------------- */

// Методы
export async function fetchVectorDbs(): Promise<VectorDbItem[]> {
  return apiGet<VectorDbItem[]>("/vector/databases");
}

export async function createVectorDb(name: string): Promise<ApiOk> {
  return apiPost<ApiOk>("/vector/create_db", { name });
}

export async function fetchVectorLayers(dbName: string): Promise<VectorLayerItem[]> {
  return apiGet<VectorLayerItem[]>(`/vector/layers/${dbName}`);
}

export async function createVectorLayer(
  dbName: string, 
  tableName: string, 
  geomType: string
): Promise<ApiOk> {
  return apiPost<ApiOk>("/vector/layers/create", { dbName, tableName, geomType });
}

// Обновленная функция с поддержкой BBOX
export async function fetchLayerData(
  dbName: string, 
  tableName: string, 
  schema: string = 'public',
  bounds?: BBox
): Promise<any> {
  let url = `/vector/layers/${dbName}/${tableName}/data?schema=${schema}`;
  
  if (bounds) {
    // Добавляем параметры границ экрана к запросу
    url += `&min_lng=${bounds.minLng}&min_lat=${bounds.minLat}&max_lng=${bounds.maxLng}&max_lat=${bounds.maxLat}`;
  }
  
  return apiGet<any>(url);
}