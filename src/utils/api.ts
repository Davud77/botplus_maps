// src/utils/api.ts

// [HARD FIX] Определение адреса API
// Мы проверяем адрес в браузере. Если это localhost, значит мы в разработке
// и должны стучаться на порт бэкенда (или фронтенда, если работает прокси).
// В данном случае стучимся на текущий хост (5580), чтобы сработал setupProxy.js

const isLocalhost = 
  typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

// Если localhost -> 'http://localhost:5580', иначе -> ''
const API_BASE = isLocalhost ? 'http://localhost:5580' : '';

console.log('API Base URL configured as:', API_BASE || '(relative path)');

/* -------------------- Общие типы -------------------- */
export interface ApiOk {
  status: "ok";
  message?: string;
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
  } | null;
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
  const contentType = res.headers.get("content-type");
  
  // [FIX] Проверка на HTML (ошибки прокси/роутинга)
  if (contentType && contentType.includes("text/html")) {
    const text = await res.text();
    // Пытаемся вытащить заголовок из HTML ошибки для ясности
    const titleMatch = text.match(/<title>(.*?)<\/title>/i);
    const title = titleMatch ? titleMatch[1] : "HTML Page returned";
    
    console.error(`API Error: Received HTML from ${url}`, text.substring(0, 200));
    throw new Error(`Ошибка API (${res.status}): Сервер вернул HTML вместо JSON по адресу ${url}. Вероятно, неправильный путь. Заголовок: ${title}`);
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let errorMessage = `Request failed: ${res.status}`;
    
    try {
      // Пытаемся распарсить JSON ошибки от бэкенда
      const jsonErr = JSON.parse(text);
      
      // [FIX] Python Flask часто возвращает 'error', а не 'message'
      if (jsonErr.message) {
        errorMessage = jsonErr.message;
      } else if (jsonErr.error) {
        errorMessage = jsonErr.error;
      } else if (jsonErr.detail) {
        errorMessage = jsonErr.detail;
      }
    } catch (e) {
      // Если не JSON, добавляем сырой текст
      if (text) errorMessage += ` | Response: ${text.substring(0, 100)}`;
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

async function apiGet<T = any>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "GET",
    credentials: "include", // Важно для кук
    headers: { "Accept": "application/json" }
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

// [FIX] Добавлен префикс /api к путям авторизации
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
// [FIX] Добавлен префикс /api для маршрутизации через прокси
export async function fetchPanoramas<T = any>(): Promise<T> {
  return apiGet<T>("/api/panoramas");
}

export async function updatePanoTags(id: number, tags: string): Promise<ApiOk> {
  return apiPut<ApiOk>(`/api/pano_info/${id}`, { tags });
}

export async function deletePano(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/api/pano_info/${id}`);
}

export async function uploadFiles<T = any>(formData: FormData): Promise<T> {
  const url = `${API_BASE}/api/upload`; // [FIX] Добавлен префикс /api
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  return handleResponse<T>(res, url);
}

// --- Ортофото ---
// [FIX] Добавлен префикс /api
export async function fetchOrthophotos(): Promise<OrthoItem[]> {
  const items = await apiGet<OrthoItem[]>("/api/orthophotos");
  
  // [FIX] Добавляем полный путь к картинке в режиме разработки
  return items.map(item => ({
    ...item,
    // Если url начинается с /api или /, добавляем API_BASE
    url: (isLocalhost && item.url.startsWith('/')) ? `${API_BASE}${item.url}` : item.url
  }));
}

// [NEW] Специальная функция для загрузки ортофотопланов
// Использует правильный endpoint /api/upload_ortho
export async function uploadOrthoFiles<T = any>(formData: FormData): Promise<T> {
  const url = `${API_BASE}/api/upload_ortho`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  return handleResponse<T>(res, url);
}

export async function deleteOrtho(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/api/orthophotos/${id}`);
}

/* -------------------- Vector / PostGIS API -------------------- */
// Здесь префикс /api уже был, оставляем как есть

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
    url += `&min_lng=${bounds.minLng}&min_lat=${bounds.minLat}&max_lng=${bounds.maxLng}&max_lat=${bounds.maxLat}`;
  }
  
  return apiGet<any>(url);
}