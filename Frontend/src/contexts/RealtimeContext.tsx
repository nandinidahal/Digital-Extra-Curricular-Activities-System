/**
 * Two WebSockets while logged in (both from the backend, both JWT-authenticated):
 *   ws/notifications/ -> unread badge, toasts, notification list refresh
 *   ws/messaging/     -> inbox socket; conversation views subscribe to its events
 * REST stays the source of truth; sockets only make the UI live.
 */
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { qk } from "@/hooks/queryKeys";
import { ReconnectingSocket, type SocketEvent } from "@/services/api/socket";
import type { AppNotification } from "@/types/api";
import { useAuth } from "./AuthContext";

type Listener = (event: SocketEvent) => void;

interface RealtimeValue {
  connected: boolean;
  subscribeMessaging: (listener: Listener) => () => void;
  sendMessaging: (payload: object) => boolean;
}

const RealtimeContext = createContext<RealtimeValue>({
  connected: false,
  subscribeMessaging: () => () => undefined,
  sendMessaging: () => false,
});

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const pathRef = useRef(location.pathname);
  useEffect(() => {
    pathRef.current = location.pathname;
  }, [location.pathname]);
  const listeners = useRef(new Set<Listener>());
  const messagingSocket = useRef<ReconnectingSocket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") return;

    const notifications = new ReconnectingSocket("/ws/notifications/", (event) => {
      const data = (event.data ?? {}) as { unread_count?: number; notification?: AppNotification };
      if (typeof data.unread_count === "number") queryClient.setQueryData(qk.notificationsUnread, data.unread_count);
      if (event.type !== "connection.ready" && event.type !== "pong") {
        void queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
      }
      if (event.type === "notification.new" && data.notification) {
        const n = data.notification;
        const viewingConversation = n.type === "message.received" && pathRef.current.startsWith(`/messages/${n.target_id}`);
        if (!viewingConversation) {
          toast(n.title, {
            description: n.message,
            action: n.action_url ? { label: "View", onClick: () => navigate(n.action_url) } : undefined,
          });
        }
        if (n.category === "friends") void queryClient.invalidateQueries({ queryKey: ["friends"] });
      }
    });

    let heartbeat: ReturnType<typeof setInterval> | null = null;
    const messaging = new ReconnectingSocket(
      "/ws/messaging/",
      (event) => {
        if (event.type === "connection.ready") {
          const interval = Number((event.data as { heartbeat_interval?: number })?.heartbeat_interval ?? 25) * 1000;
          if (heartbeat) clearInterval(heartbeat);
          heartbeat = setInterval(() => {
            if (document.visibilityState === "visible") messaging.send({ type: "presence.heartbeat" });
          }, interval);
        }
        if (["message.new", "message.deleted", "conversation.read", "message.read", "conversation.updated"].includes(event.type)) {
          void queryClient.invalidateQueries({ queryKey: ["messaging", "conversations"] });
          void queryClient.invalidateQueries({ queryKey: qk.messagingUnread });
        }
        listeners.current.forEach((listener) => listener(event));
      },
      setConnected,
    );
    messagingSocket.current = messaging;
    notifications.start();
    messaging.start();
    return () => {
      if (heartbeat) clearInterval(heartbeat);
      notifications.stop();
      messaging.stop();
      messagingSocket.current = null;
    };
  }, [status, queryClient, navigate]);

  const subscribeMessaging = useCallback((listener: Listener) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const sendMessaging = useCallback((payload: object) => messagingSocket.current?.send(payload) ?? false, []);

  const value = useMemo(() => ({ connected, subscribeMessaging, sendMessaging }), [connected, subscribeMessaging, sendMessaging]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export const useRealtime = () => useContext(RealtimeContext);
