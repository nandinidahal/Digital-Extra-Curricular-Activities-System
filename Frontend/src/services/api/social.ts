/** Social module: /api/social/ */
import type { Comment, LikeState, Paginated, Post, PostShare, PostType, PostVisibility, SocialReport, SocialReportReason } from "@/types/api";
import { api, toFormData } from "./client";

export interface PostInput {
  content?: string;
  post_type?: PostType;
  visibility?: PostVisibility;
  images?: File[];
}

function postBody(input: PostInput) {
  if (input.images && input.images.length) return toFormData({ ...input });
  const { images: _ignored, ...json } = input;
  return json;
}

export interface FeedParams {
  page?: number;
  scope?: "all" | "friends";
  post_type?: PostType;
  shared_type?: "announcement" | "achievement";
}

export const socialApi = {
  feed: (params: FeedParams) => api.get<Paginated<Post>>("/social/feed/", { params }),
  posts: (params: { page?: number; post_type?: PostType }) => api.get<Paginated<Post>>("/social/posts/", { params }),
  myPosts: (page: number) => api.get<Paginated<Post>>("/social/me/posts/", { params: { page } }),
  userPosts: (userId: string, page: number) => api.get<Paginated<Post>>(`/social/users/${userId}/posts/`, { params: { page } }),
  post: (id: string) => api.get<{ post: Post }>(`/social/posts/${id}/`),
  createPost: (input: PostInput) => api.post<{ post: Post }>("/social/posts/", postBody(input)),
  updatePost: (id: string, input: PostInput) => api.patch<{ post: Post }>(`/social/posts/${id}/`, postBody(input)),
  deletePost: (id: string) => api.delete(`/social/posts/${id}/`),
  removeMedia: (postId: string, mediaId: string) => api.delete<{ post: Post }>(`/social/posts/${postId}/media/${mediaId}/`),
  like: (id: string) => api.post<LikeState>(`/social/posts/${id}/like/`),
  unlike: (id: string) => api.delete<LikeState>(`/social/posts/${id}/like/`),
  comments: (postId: string, page: number) => api.get<Paginated<Comment>>(`/social/posts/${postId}/comments/`, { params: { page } }),
  addComment: (postId: string, content: string) => api.post<{ comment: Comment }>(`/social/posts/${postId}/comments/`, { content }),
  replies: (commentId: string, page: number) => api.get<Paginated<Comment>>(`/social/comments/${commentId}/replies/`, { params: { page } }),
  reply: (commentId: string, content: string) => api.post<{ comment: Comment }>(`/social/comments/${commentId}/reply/`, { content }),
  editComment: (commentId: string, content: string) => api.patch<{ comment: Comment }>(`/social/comments/${commentId}/`, { content }),
  deleteComment: (commentId: string) => api.delete(`/social/comments/${commentId}/`),
  likeComment: (commentId: string) => api.post<LikeState>(`/social/comments/${commentId}/like/`),
  unlikeComment: (commentId: string) => api.delete<LikeState>(`/social/comments/${commentId}/like/`),
  sharePost: (postId: string, caption = "") => api.post<{ share: PostShare & { share_count: number } }>(`/social/posts/${postId}/share/`, caption ? { caption } : {}),
  shareResource: (resource_type: "announcement" | "achievement", resource_id: string, caption = "", visibility: Exclude<PostVisibility, "private"> = "public") =>
    api.post<{ post: Post }>("/social/shares/", { resource_type, resource_id, caption, visibility }),
  deleteShare: (shareId: string) => api.delete(`/social/shares/${shareId}/`),
  myShares: (page: number) => api.get<Paginated<PostShare>>("/social/me/shares/", { params: { page } }),
  report: (content_type: "post" | "comment", object_id: string, reason: SocialReportReason, description = "") =>
    api.post("/social/reports/", { content_type, object_id, reason, description }),
  reports: (status: string, page: number) => api.get<Paginated<SocialReport>>("/social/reports/", { params: { status: status || undefined, page } }),
  reviewReport: (id: string, body: { status: string; review_comments?: string; action?: "none" | "content_removed" }) =>
    api.patch<{ report: SocialReport }>(`/social/reports/${id}/`, body),
};
