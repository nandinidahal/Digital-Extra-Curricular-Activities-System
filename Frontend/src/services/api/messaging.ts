/** Messaging module: /api/messaging/ (REST). Real-time events: see contexts/RealtimeContext. */
import type { Conversation, CursorPaginated, Message, MessagingState, Paginated } from "@/types/api";
import { api, toFormData } from "./client";

export const messagingApi = {
  conversations: (page: number, archived = false) =>
    api.get<Paginated<Conversation>>("/messaging/conversations/", { params: { page, archived } }),
  start: (userId: string) => api.post<Conversation>("/messaging/conversations/", { user_id: userId }),
  conversation: (id: string) => api.get<Conversation>(`/messaging/conversations/${id}/`),
  mute: (id: string, is_muted: boolean) => api.patch<Conversation>(`/messaging/conversations/${id}/mute/`, { is_muted }),
  archive: (id: string, is_archived: boolean) => api.patch<Conversation>(`/messaging/conversations/${id}/archive/`, { is_archived }),
  /** Newest first. `cursorUrl` is the absolute `pagination.next` link for older messages. */
  messages: (id: string, cursorUrl?: string | null) =>
    cursorUrl ? api.get<CursorPaginated<Message>>(cursorUrl) : api.get<CursorPaginated<Message>>(`/messaging/conversations/${id}/messages/`),
  send: (id: string, body: { content: string; client_id: string; reply_to_id?: string; attachments?: File[] }) => {
    const payload = body.attachments && body.attachments.length ? toFormData(body) : { content: body.content, client_id: body.client_id, ...(body.reply_to_id ? { reply_to_id: body.reply_to_id } : {}) };
    return api.post<{ message: Message; messaging: MessagingState }>(`/messaging/conversations/${id}/messages/`, payload);
  },
  edit: (messageId: string, content: string) => api.patch<Message>(`/messaging/messages/${messageId}/`, { content }),
  deleteForMe: (messageId: string) => api.post(`/messaging/messages/${messageId}/delete-for-me/`),
  deleteForEveryone: (messageId: string) => api.post<Message>(`/messaging/messages/${messageId}/delete-for-everyone/`),
  react: (messageId: string, reaction_type: string) => api.post<Message>(`/messaging/messages/${messageId}/reactions/`, { reaction_type }),
  unreact: (messageId: string) => api.delete<Message>(`/messaging/messages/${messageId}/reactions/`),
  markRead: (id: string) => api.post<{ unread_count: number }>(`/messaging/conversations/${id}/read/`, {}),
  totalUnread: () => api.get<{ unread_count: number }>("/messaging/unread-count/"),
  search: (id: string, q: string) => api.get<Paginated<Message>>(`/messaging/conversations/${id}/search/`, { params: { q } }),
};
