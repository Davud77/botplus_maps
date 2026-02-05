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
export async function fetchOrthophotos<T = any>(): Promise<T> {
  return apiGet<T>("/orthophotos");
}

export async function deleteOrtho(id: number): Promise<ApiOk> {
  return apiDelete<ApiOk>(`/orthophotos/${id}`);
}