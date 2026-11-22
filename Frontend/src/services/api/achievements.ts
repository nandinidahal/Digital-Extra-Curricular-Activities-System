/** Achievements module: /api/achievements/ and /api/achievement-categories/ */
import type {
  Achievement, AchievementHistoryItem, AchievementLevel, AchievementStats, AchievementType, Category,
  Evidence, Paginated, VerificationStatus, Visibility,
} from "@/types/api";
import { api, toFormData } from "./client";

export interface AchievementFilters {
  page?: number;
  q?: string;
  category?: string;
  achievement_type?: AchievementType | "";
  level?: AchievementLevel | "";
  status?: VerificationStatus | "";
  featured?: boolean;
  skill?: string;
  ordering?: "newest" | "oldest" | "submitted" | "-submitted" | "title";
}

export interface AchievementInput {
  title?: string;
  description?: string;
  category?: string | null;
  achievement_type?: AchievementType;
  organization?: string;
  event_name?: string;
  related_announcement?: string | null;
  achievement_date?: string;
  location?: string;
  level?: AchievementLevel;
  position?: string;
  skills?: string[];
  visibility?: Visibility;
}

const clean = (p: AchievementFilters) =>
  Object.fromEntries(Object.entries(p).filter(([, v]) => v !== "" && v !== undefined));

export const achievementsApi = {
  list: (params: AchievementFilters) => api.get<Paginated<Achievement>>("/achievements/", { params: clean(params) }),
  search: (params: AchievementFilters) => api.get<Paginated<Achievement>>("/achievements/search/", { params: clean(params) }),
  mine: (params: AchievementFilters) => api.get<Paginated<Achievement>>("/achievements/me/", { params: clean(params) }),
  ofUser: (userId: string, page: number) => api.get<Paginated<Achievement>>(`/achievements/users/${userId}/`, { params: { page } }),
  featured: (userId?: string) => api.get<Paginated<Achievement>>("/achievements/featured/", { params: userId ? { user_id: userId } : {} }),
  get: (id: string) => api.get<{ achievement: Achievement }>(`/achievements/${id}/`),
  create: (input: AchievementInput) => api.post<{ achievement: Achievement }>("/achievements/", input),
  update: (id: string, input: AchievementInput) => api.patch<{ achievement: Achievement }>(`/achievements/${id}/`, input),
  remove: (id: string) => api.delete(`/achievements/${id}/`),
  uploadEvidence: (id: string, files: File[]) => api.post<{ evidence: Evidence[] }>(`/achievements/${id}/evidence/`, toFormData({ files })),
  deleteEvidence: (evidenceId: string) => api.delete(`/achievements/evidence/${evidenceId}/`),
  feature: (id: string) => api.post<{ achievement: Achievement }>(`/achievements/${id}/feature/`),
  unfeature: (id: string) => api.delete<{ achievement: Achievement }>(`/achievements/${id}/feature/`),
  resubmit: (id: string, note = "") => api.post<{ achievement: Achievement }>(`/achievements/${id}/resubmit/`, note ? { note } : {}),
  history: (id: string) => api.get<{ history: AchievementHistoryItem[] }>(`/achievements/${id}/history/`),
  stats: (scope?: "platform") => api.get<{ scope: string; statistics: AchievementStats }>("/achievements/stats/", { params: scope ? { scope } : {} }),
  pending: (page: number) => api.get<Paginated<Achievement>>("/achievements/pending/", { params: { page } }),
  verify: (id: string, comments = "") => api.post<{ achievement: Achievement }>(`/achievements/${id}/verify/`, comments ? { comments } : {}),
  reject: (id: string, comments: string) => api.post<{ achievement: Achievement }>(`/achievements/${id}/reject/`, { comments }),
  requestInformation: (id: string, comments: string) =>
    api.post<{ achievement: Achievement }>(`/achievements/${id}/request-information/`, { comments }),
  categories: () => api.get<{ results: Category[] }>("/achievement-categories/", { skipAuth: true }),
};
