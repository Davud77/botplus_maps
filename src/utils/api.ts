// src/utils/api.ts

// Ходим только на свой бэкенд того же origin (Flask отдаёт /api/*)
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
    credentials: "include",
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

/* -------------------- Auth API -------------------- */
// Ответ /api/auth/me
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

/* -------------------- Примеры прикладных вызовов -------------------- */
/** Панорамы (предполагается эндпоинт на сервере /api/panoramas) */
export async function fetchPanoramas<T = any>(): Promise<T> {
  return apiGet<T>("/panoramas");
}

/** Загрузка файлов (POST /api/upload). Важно: без ручной установки Content-Type — его выставит браузер. */
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
