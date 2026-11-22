/**
 * Where the JWT pair lives.
 *
 * The backend returns access + refresh tokens in the JSON body (no httpOnly cookie option),
 * so they must be kept by the browser. "Remember me" -> localStorage (survives restarts);
 * otherwise sessionStorage (cleared when the browser session ends). The access token is also
 * cached in memory. Tokens are never logged or put in URLs (WebSockets use a subprotocol).
 */
import type { Tokens } from "@/types/api";

const KEY = "deas.auth";

type Stored = Tokens & { remember: boolean };

let memory: Stored | null = null;

function read(): Stored | null {
  if (memory) return memory;
  for (const store of [localStorage, sessionStorage]) {
    try {
      const raw = store.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Stored;
        if (parsed.access && parsed.refresh) {
          memory = parsed;
          return parsed;
        }
      }
    } catch {
      /* corrupted or blocked storage: treat as logged out */
    }
  }
  return null;
}

export const tokenStorage = {
  get(): Tokens | null {
    const stored = read();
    return stored ? { access: stored.access, refresh: stored.refresh } : null;
  },
  remember(): boolean {
    return read()?.remember ?? false;
  },
  set(tokens: Tokens, remember?: boolean): void {
    const keep = remember ?? read()?.remember ?? false;
    memory = { ...tokens, remember: keep };
    const target = keep ? localStorage : sessionStorage;
    const other = keep ? sessionStorage : localStorage;
    try {
      target.setItem(KEY, JSON.stringify(memory));
      other.removeItem(KEY);
    } catch {
      /* storage unavailable (private mode): keep in memory only */
    }
  },
  clear() {
    memory = null;
    try {
      localStorage.removeItem(KEY);
      sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  },
};

/** Seconds until the JWT expires (negative when expired). Never verifies: the server does that. */
export function secondsUntilExpiry(jwt: string): number {
  try {
    const payload = JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: number };
    return (payload.exp ?? 0) - Date.now() / 1000;
  } catch {
    return -1;
  }
}
