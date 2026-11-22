/**
 * Reconnecting WebSocket using the backend's JWT subprotocol auth:
 *   new WebSocket(url, ["deas.jwt", accessToken])
 * On close 4401 (not authenticated / token expired) the access token is refreshed first.
 * Other closes back off exponentially (1s .. 30s). The token is never put in the URL.
 */
import { getFreshAccessToken, refreshAccessToken } from "./client";
import { WS_BASE_URL } from "./config";

export interface SocketEvent {
  type: string;
  data?: unknown;
  conversation_id?: string;
  [key: string]: unknown;
}

export class ReconnectingSocket {
  private socket: WebSocket | null = null;
  private attempts = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;
  private readonly path: string;
  private readonly onEvent: (event: SocketEvent) => void;
  private readonly onStatus?: (connected: boolean) => void;

  constructor(path: string, onEvent: (event: SocketEvent) => void, onStatus?: (connected: boolean) => void) {
    this.path = path;
    this.onEvent = onEvent;
    this.onStatus = onStatus;
  }

  start() {
    this.disposed = false;
    void this.connect();
  }

  stop() {
    this.disposed = true;
    if (this.timer) clearTimeout(this.timer);
    this.socket?.close(1000);
    this.socket = null;
  }

  send(payload: object): boolean {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  private async connect(forceRefresh = false) {
    if (this.disposed) return;
    const token = forceRefresh ? await refreshAccessToken() : await getFreshAccessToken();
    if (!token || this.disposed) return; // logged out
    let socket: WebSocket;
    try {
      socket = new WebSocket(`${WS_BASE_URL}${this.path}`, ["deas.jwt", token]);
    } catch {
      this.schedule();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.attempts = 0;
      this.onStatus?.(true);
    };
    socket.onmessage = (message) => {
      try {
        this.onEvent(JSON.parse(message.data as string) as SocketEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = (event) => {
      this.onStatus?.(false);
      if (this.disposed) return;
      if (event.code === 4403) return; // account not allowed: do not hammer the server
      this.schedule(event.code === 4401);
    };
  }

  private schedule(refresh = false) {
    if (this.disposed) return;
    const delay = refresh && this.attempts === 0 ? 200 : Math.min(30_000, 1000 * 2 ** this.attempts);
    this.attempts += 1;
    this.timer = setTimeout(() => void this.connect(refresh), delay);
  }
}
