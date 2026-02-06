// src/utils/api.ts

// [FIX] Определяем правильный адрес API
// В разработке (локально) используем прямой адрес бэкенда (5580)
// В продакшене (Docker) используем относительный путь
const API_BASE = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:5580' 
  : '';

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

/* -------------------- Низкоуровневые вызовы (с обработкой ошибок) -------------------- */

async function handleResponse<T>(res: Response, url: string): Promise<T> {
  // [FIX] Проверка на HTML (ошибка "Unexpected token <")
  const contentType = res.headers.get("content-type");
  if (contentType && contentType.includes("text/html")) {
    const text = await res.text();
    // Пытаемся вытащить заголовок из HTML ошибки для ясности
    const titleMatch = text.match(/<title>(.*?)<\/title>/i);
    const title = titleMatch ? titleMatch[1] : "HTML Page returned";
    throw new Error(`Ошибка API (${res.status}): Сервер вернул HTML вместо JSON по адресу ${url}. Вероятно, неправильный путь. Заголовок: ${title}`);
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Request failed: ${res.status} ${text}`);
  }

  return res.json();
}

async function apiGet<T = any>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "GET",
    credentials: "include", // Важно для кук
  });
  return handleResponse<T>(res, url);
}

async function apiPost<T = any>(path: string, body?: any): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res, url);
}

async function apiPut<T = any>(path: string, body?: any): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res, url);
}

async function apiDelete<T = any>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  return handleResponse<T>(res, url);
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

// [FIX] Добавлен префикс /api к путям авторизации, так как в app.py url_prefix="/api/auth"
export async function authMe(): Promise<MeResponse> {
  return apiGet<MeResponse>("/api/auth/me");
}

export async function authLogin(username: string, password: string): Promise<ApiResp> {
  return apiPost<ApiResp>("/api/auth/login", { username, password });
}

export async function authLogout(): Promise<ApiResp> {
  return apiPost<ApiResp>("/api/auth/logout", {});
}

/* -------------------- Data API -------------------- */

// --- Панорамы ---
// [NOTE] В app.py pano_blueprint зарегистрирован без префикса, поэтому пути от корня
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
  const url = `${API_BASE}/upload`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  return handleResponse<T>(res, url);
}

// --- Ортофото ---
// [NOTE] В app.py ortho_blueprint зарегистрирован без префикса
export async function fetchOrthophotos(): Promise<OrthoItem[]> {
  return apiGet<OrthoItem[]>("/orthophotos");
}

export async function deleteOrtho(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/orthophotos/${id}`);
}

/* -------------------- Vector / PostGIS API -------------------- */
// [NOTE] В app.py vector_bp зарегистрирован с префиксом /api

export async function fetchVectorDbs(): Promise<VectorDbItem[]> {
  return apiGet<VectorDbItem[]>("/api/vector/databases");
}

export async function createVectorDb(name: string): Promise<ApiOk> {
  return apiPost<ApiOk>("/api/vector/create_db", { name });
}

export async function fetchVectorLayers(dbName: string): Promise<VectorLayerItem[]> {
  return apiGet<VectorLayerItem[]>(`/api/vector/layers/${dbName}`);
}

export async function createVectorLayer(
  dbName: string, 
  tableName: string, 
  geomType: string
): Promise<ApiOk> {
  return apiPost<ApiOk>("/api/vector/layers/create", { dbName, tableName, geomType });
}

// Обновленная функция с поддержкой BBOX
export async function fetchLayerData(
  dbName: string, 
  tableName: string, 
  schema: string = 'public',
  bounds?: BBox
): Promise<any> {
  let url = `/api/vector/layers/${dbName}/${tableName}/data?schema=${schema}`;
  
  if (bounds) {
    // Добавляем параметры границ экрана к запросу
    url += `&min_lng=${bounds.minLng}&min_lat=${bounds.minLat}&max_lng=${bounds.maxLng}&max_lat=${bounds.maxLat}`;
  }
  
  return apiGet<any>(url);
}