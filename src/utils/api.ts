// frontend/src/utils/api.ts

// Единый клиент для вызовов бэкенда.
// По умолчанию ходим на тот же origin (Flask/прокси отдают /api/*).
// При необходимости можно переопределить базу через .env: VITE_API_BASE_URL="https://api.botplus.ru"
//
// Важно:
//  - всегда credentials: 'include' (куки access/refresh идут автоматически);
//  - НИКОГДА не выставляй заголовок 'Cookie' вручную;
//  - все маршруты начинаются с "/api/*" (см. server/app.py).

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

const RAW_BASE =
  (import.meta as any)?.env?.VITE_API_BASE_URL?.toString()?.trim() || "";

// Если RAW_BASE пуст — используем тот же origin (относительные пути).
export const API_BASE: string = RAW_BASE;

/** Корректно склеивает base и path. */
function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = API_BASE.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

/* -------------------- Общие типы -------------------- */
export interface ApiOk {
  status: "ok";
  [k: string]: any;
}

export interface ApiError {
  status: "error" | "fail";
  message: string;
  [k: string]: any;
}

export type ApiResp = ApiOk | ApiError;

/* -------------------- Низкоуровневые вызовы -------------------- */

async function request<T = any>(
  path: string,
  {
    method = "GET",
    body,
    headers,
    asForm = false,
    signal,
  }: {
    method?: HttpMethod;
    body?: any;
    headers?: Record<string, string>;
    asForm?: boolean; // true — если отправляем FormData (multipart/form-data)
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const url = buildUrl(path);

  const init: RequestInit = {
    method,
    credentials: "include",
    // CORS корректно обрабатывает сам сервер (flask-cors); здесь просто не мешаем.
    headers: {
      ...(headers || {}),
    },
    signal,
  };

  if (body != null) {
    if (asForm && body instanceof FormData) {
      // Для FormData не проставляем Content-Type — браузер добавит boundary сам.
      init.body = body;
    } else {
      init.headers = {
        "Content-Type": "application/json",
        ...(init.headers as Record<string, string>),
      };
      init.body = JSON.stringify(body);
    }
  }

  const res = await fetch(url, init);

  if (!res.ok) {
    // Пробуем вытащить пояснение с сервера
    let detail: unknown = undefined;
    const ct = res.headers.get("content-type") || "";
    try {
      detail = ct.includes("application/json") ? await res.json() : await res.text();
    } catch {
      /* ignore */
    }
    const err = new Error(`HTTP ${res.status} ${res.statusText} @ ${path}`);
    (err as any).status = res.status;
    (err as any).detail = detail;
    throw err;
  }

  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

async function apiGet<T = any>(path: string, opts: { signal?: AbortSignal } = {}): Promise<T> {
  return request<T>(path, { method: "GET", ...opts });
}

async function apiPost<T = any>(
  path: string,
  body?: any,
  opts: { headers?: Record<string, string>; signal?: AbortSignal } = {},
): Promise<T> {
  return request<T>(path, { method: "POST", body, headers: opts.headers, signal: opts.signal });
}

async function apiUpload<T = any>(path: string, form: FormData, opts: { signal?: AbortSignal } = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: form, asForm: true, signal: opts.signal });
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

export const authMe = (): Promise<MeResponse> => apiGet("/api/auth/me");

export const authLogin = (username: string, password: string): Promise<ApiResp> =>
  apiPost<ApiResp>("/api/auth/login", { username, password });

export const authLogout = (): Promise<ApiResp> => apiPost<ApiResp>("/api/auth/logout", {});

/* -------------------- Прикладные вызовы -------------------- */

// Панорамы (серверные маршруты под префиксом /api)
export const fetchPanoramas = <T = any>(): Promise<T> => apiGet<T>("/api/panoramas");
export const uploadPano =   <T = any>(form: FormData): Promise<T> => apiUpload<T>("/api/panoramas", form);

// Ортофото
export const fetchOrthophotos = <T = any>(): Promise<T> => apiGet<T>("/api/orthophotos");
export const uploadOrtho      = <T = any>(form: FormData): Promise<T> => apiUpload<T>("/api/orthophotos", form);

// Универсальная загрузка (произвольный путь под /api/*)
export const uploadTo = <T = any>(path: string, form: FormData): Promise<T> => apiUpload<T>(path, form);

// Health (можно использовать в проверках готовности)
export const apiHealth = () => apiGet<{ ok: boolean }>("/api/health");
