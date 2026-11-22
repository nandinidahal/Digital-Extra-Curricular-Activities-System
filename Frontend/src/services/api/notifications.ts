/** Notifications module: /api/notifications/ (REST). Live events: ws/notifications/. */
import type { AppNotification, NotificationCategory, NotificationPreferences, Paginated } from "@/types/api";
import { api } from "./client";

export const notificationsApi = {
  list: (params: { page?: number; is_read?: boolean; category?: NotificationCategory }) =>
    api.get<Paginated<AppNotification>>("/notifications/", { params }),
  unreadCount: () => api.get<{ unread_count: number }>("/notifications/unread-count/"),
  markRead: (id: string) => api.post<{ notification: AppNotification; unread_count: number }>(`/notifications/${id}/read/`),
  markUnread: (id: string) => api.post<{ notification: AppNotification; unread_count: number }>(`/notifications/${id}/unread/`),
  markAllRead: () => api.post<{ updated: number; unread_count: number }>("/notifications/read-all/"),
  remove: (id: string) => api.delete<{ unread_count: number }>(`/notifications/${id}/`),
  clear: (readOnly: boolean) => api.delete<{ deleted: number; unread_count: number }>("/notifications/clear/", { params: readOnly ? { read_only: true } : {} }),
  preferences: () => api.get<{ preferences: NotificationPreferences }>("/notifications/preferences/"),
  updatePreferences: (body: Partial<Omit<NotificationPreferences, "updated_at" | "always_on">>) =>
    api.patch<{ preferences: NotificationPreferences }>("/notifications/preferences/", body),
};
