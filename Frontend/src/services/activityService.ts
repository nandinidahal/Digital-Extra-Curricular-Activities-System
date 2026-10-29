import api from "./api";
import type { Activity, Announcement, Category, Paginated } from "../types";

export const activityService = {
  list(params?: { search?: string; category?: number; status?: string; page?: number }) {
    return api.get<Paginated<Activity>>("/activities/", { params }).then((r) => r.data);
  },
  get(id: number | string) {
    return api.get<Activity>(`/activities/${id}/`).then((r) => r.data);
  },
  categories() {
    return api.get<Paginated<Category>>("/categories/").then((r) => r.data.results);
  },
  announcements() {
    return api.get<Paginated<Announcement>>("/announcements/").then((r) => r.data.results);
  },
};
