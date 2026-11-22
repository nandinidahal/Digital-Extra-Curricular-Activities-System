/** Announcements module: /api/announcements/ and /api/categories/ */
import type {
  ActivityType, AnnouncementBookmark, AnnouncementCard, AnnouncementDetail, AnnouncementReport,
  AnnouncementReportReason, AnnouncementStatus, Category, Paginated, Visibility,
} from "@/types/api";
import { api, toFormData } from "./client";

export interface AnnouncementFilters {
  page?: number;
  q?: string;
  category?: string;
  activity_type?: ActivityType | "";
  location?: string;
  organizer?: string;
  start_from?: string;
  start_to?: string;
  when?: "upcoming" | "past" | "ongoing" | "";
  registration_open?: boolean;
  status?: AnnouncementStatus | "";
  ordering?: "newest" | "oldest" | "start" | "-start" | "deadline" | "title" | "updated";
}

export interface AnnouncementInput {
  title?: string;
  short_description?: string;
  description?: string;
  category?: string | null;
  activity_type?: ActivityType;
  organizer_name?: string;
  organizer_email?: string;
  organizer_phone?: string;
  contact_information?: string;
  show_contact_details?: boolean;
  location?: string;
  online_link?: string;
  start_datetime?: string | null;
  end_datetime?: string | null;
  registration_deadline?: string | null;
  registration_link?: string;
  eligibility_criteria?: string;
  requirements?: string;
  visibility?: Visibility;
  status?: "draft" | "published"; // create only
  cover_image?: File;
  remove_cover_image?: boolean;
}

function clean(params: AnnouncementFilters) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== false));
}

function body(input: AnnouncementInput) {
  return input.cover_image ? toFormData({ ...input }) : input;
}

export const announcementsApi = {
  publicList: (params: Pick<AnnouncementFilters, "page">) =>
    api.get<Paginated<AnnouncementCard>>("/announcements/public/", { params: clean(params) }),
  list: (params: AnnouncementFilters) => api.get<Paginated<AnnouncementCard>>("/announcements/", { params: clean(params) }),
  search: (params: AnnouncementFilters) => api.get<Paginated<AnnouncementCard>>("/announcements/search/", { params: clean(params) }),
  mine: (status: AnnouncementStatus | "", page: number) =>
    api.get<Paginated<AnnouncementCard>>(status ? `/announcements/me/${status === "draft" ? "drafts" : status}/` : "/announcements/me/", { params: { page } }),
  get: (id: string) => api.get<{ announcement: AnnouncementDetail }>(`/announcements/${id}/`),
  create: (input: AnnouncementInput) => api.post<{ announcement: AnnouncementDetail }>("/announcements/", body(input)),
  update: (id: string, input: AnnouncementInput) => api.patch<{ announcement: AnnouncementDetail }>(`/announcements/${id}/`, body(input)),
  remove: (id: string) => api.delete(`/announcements/${id}/`),
  publish: (id: string) => api.post<{ announcement: AnnouncementDetail }>(`/announcements/${id}/publish/`),
  archive: (id: string) => api.post<{ announcement: AnnouncementDetail }>(`/announcements/${id}/archive/`),
  restore: (id: string) => api.post<{ announcement: AnnouncementDetail }>(`/announcements/${id}/restore/`),
  bookmark: (id: string) => api.post<{ is_bookmarked: boolean }>(`/announcements/${id}/bookmark/`),
  unbookmark: (id: string) => api.delete<{ is_bookmarked: boolean }>(`/announcements/${id}/bookmark/`),
  bookmarks: (page: number) => api.get<Paginated<AnnouncementBookmark>>("/announcements/bookmarks/", { params: { page } }),
  report: (id: string, reason: AnnouncementReportReason, description = "") =>
    api.post(`/announcements/${id}/report/`, { reason, description }),
  reports: (status: string, page: number) =>
    api.get<Paginated<AnnouncementReport>>("/announcements/reports/", { params: { status: status || undefined, page } }),
  reviewReport: (id: string, body: { status: string; review_comments?: string; action?: "none" | "archived" }) =>
    api.patch<{ report: AnnouncementReport }>(`/announcements/reports/${id}/`, body),
  categories: () => api.get<{ results: Category[] }>("/categories/", { skipAuth: true }),
};
