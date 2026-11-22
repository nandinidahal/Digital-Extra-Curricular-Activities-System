const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

export const API_BASE_URL = raw.replace(/\/+$/, "");

export const WS_BASE_URL = (
  (import.meta.env.VITE_WS_BASE_URL as string | undefined) ?? API_BASE_URL.replace(/^http/, "ws")
).replace(/\/+$/, "");
