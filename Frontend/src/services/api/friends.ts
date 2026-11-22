/** Friends module: /api/friends/ */
import type { BlockedUser, DiscoverUser, Friend, FriendCard, FriendRequest, Paginated, Relationship } from "@/types/api";
import { api } from "./client";

export const friendsApi = {
  list: (page: number) => api.get<Paginated<Friend>>("/friends/", { params: { page } }),
  count: () => api.get<{ friend_count: number }>("/friends/count/"),
  status: (userId: string) => api.get<Relationship>(`/friends/status/${userId}/`),
  mutual: (userId: string, page: number) => api.get<Paginated<FriendCard>>(`/friends/mutual/${userId}/`, { params: { page } }),
  discover: (page: number) => api.get<Paginated<DiscoverUser>>("/friends/discover/", { params: { page } }),
  received: (page: number) => api.get<Paginated<FriendRequest>>("/friends/requests/received/", { params: { page } }),
  sent: (page: number) => api.get<Paginated<FriendRequest>>("/friends/requests/sent/", { params: { page } }),
  send: (receiverId: string) => api.post<{ request: FriendRequest; auto_accepted: boolean }>("/friends/requests/", { receiver_id: receiverId }),
  accept: (requestId: string) => api.post(`/friends/requests/${requestId}/accept/`),
  reject: (requestId: string) => api.post(`/friends/requests/${requestId}/reject/`),
  cancel: (requestId: string) => api.post(`/friends/requests/${requestId}/cancel/`),
  remove: (userId: string) => api.delete(`/friends/${userId}/`),
  blocked: (page: number) => api.get<Paginated<BlockedUser>>("/friends/blocked/", { params: { page } }),
  block: (userId: string) => api.post("/friends/blocked/", { user_id: userId }),
  unblock: (userId: string) => api.delete(`/friends/blocked/${userId}/`),
};
