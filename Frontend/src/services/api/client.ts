/**
 * The single Axios client for the whole app.
 *
 * - Adds `Authorization: Bearer <access>` (unless `skipAuth`).
 * - Refreshes the access token BEFORE it expires (some endpoints accept visitors and would
 *   otherwise silently treat an expired token as "anonymous") and again on a 401.
 * - Refresh is single-flight: concurrent requests wait for one refresh, because the backend
 *   rotates and blacklists refresh tokens (a second parallel refresh would fail).
 * - When the session cannot be renewed, tokens are cleared and a `deas:session-expired` event
 *   is dispatched; AuthContext logs the user out and the router sends them to /login.
 * - Unwraps the `{success, message, data}` envelope via the helpers at the bottom.
 */
import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";
import type { ApiSuccess, Tokens } from "@/types/api";
import { secondsUntilExpiry, tokenStorage } from "../auth/tokenStorage";
import { API_BASE_URL } from "./config";
import { toApiError } from "./errors";

declare module "axios" {
  interface AxiosRequestConfig {
    skipAuth?: boolean;
    _retried?: boolean;
  }
}

export const http = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

let refreshing: Promise<string | null> | null = null;

export const SESSION_EXPIRED_EVENT = "deas:session-expired";

/** Exchange the refresh token for a new pair. Resolves to the new access token or null. */
export function refreshAccessToken(): Promise<string | null> {
  if (refreshing) return refreshing;
  const current = tokenStorage.get();
  if (!current?.refresh) return Promise.resolve(null);
  refreshing = axios
    .post<ApiSuccess<{ tokens: Tokens }>>(`${API_BASE_URL}/api/auth/token/refresh/`, { refresh: current.refresh })
    .then((response) => {
      const tokens = response.data.data.tokens;
      tokenStorage.set({ access: tokens.access, refresh: tokens.refresh ?? current.refresh });
      return tokens.access;
    })
    .catch((error) => {
      // Only a definitive rejection ends the session; a network blip keeps the tokens.
      if (axios.isAxiosError(error) && error.response && [400, 401].includes(error.response.status)) {
        tokenStorage.clear();
        window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      }
      return null;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** A valid access token, refreshed if it expires within 30 seconds. */
export async function getFreshAccessToken(): Promise<string | null> {
  const tokens = tokenStorage.get();
  if (!tokens) return null;
  if (secondsUntilExpiry(tokens.access) > 30) return tokens.access;
  return refreshAccessToken();
}

http.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (config.skipAuth) return config;
  const token = await getFreshAccessToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

const TOKEN_ERROR_CODES = new Set(["token_not_valid", "not_authenticated", "authentication_failed"]);

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as AxiosRequestConfig | undefined;
    const status = error.response?.status;
    const code = error.response?.data?.code;
    if (status === 401 && config && !config.skipAuth && !config._retried && TOKEN_ERROR_CODES.has(code) && tokenStorage.get()) {
      config._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        config.headers = { ...(config.headers ?? {}), Authorization: `Bearer ${token}` };
        return http.request(config);
      }
    }
    return Promise.reject(toApiError(error));
  },
);

// ---------------------------------------------------------------------------
// Envelope helpers
// ---------------------------------------------------------------------------
export interface Result<T> {
  data: T;
  message: string;
  status: number;
}

async function unwrap<T>(promise: Promise<{ data: ApiSuccess<T>; status: number }>): Promise<Result<T>> {
  const response = await promise;
  return { data: response.data.data, message: response.data.message, status: response.status };
}

export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) => unwrap<T>(http.get(url, config)),
  post: <T>(url: string, body?: unknown, config?: AxiosRequestConfig) => unwrap<T>(http.post(url, body, config)),
  patch: <T>(url: string, body?: unknown, config?: AxiosRequestConfig) => unwrap<T>(http.patch(url, body, config)),
  delete: <T>(url: string, config?: AxiosRequestConfig) => unwrap<T>(http.delete(url, config)),
};

/** Build multipart/form-data; arrays become repeated keys (DRF ListField / getlist). */
export function toFormData(values: Record<string, unknown>): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) value.forEach((item) => form.append(key, item instanceof Blob ? item : String(item)));
    else if (value instanceof Blob) form.append(key, value);
    else if (value === null) form.append(key, "");
    else form.append(key, String(value));
  }
  return form;
}

/** Strip undefined and empty-string optional values so strict serializers do not complain. */
export function compact<T extends Record<string, unknown>>(values: T): Partial<T> {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined)) as Partial<T>;
}
