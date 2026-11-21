
// import api from "./api";
// import type {
//   Announcement,
//   AnnouncementListResponse,
// } from "../types/announcement";

// const getResults = (
//   data: Announcement[] | AnnouncementListResponse
// ): Announcement[] => {
//   if (Array.isArray(data)) {
//     return data;
//   }

//   return data.results ?? [];
// };

// const announcementService = {
//   async getLatestAnnouncements(): Promise<Announcement[]> {
//     const response = await api.get<
//       Announcement[] | AnnouncementListResponse
//     >("/announcements/latest/");

//     return getResults(response.data);
//   },

//   async getAllAnnouncements(): Promise<Announcement[]> {
//     const response = await api.get<
//       Announcement[] | AnnouncementListResponse
//     >("/announcements/");

//     return getResults(response.data);
//   },

//   async getAnnouncement(id: number): Promise<Announcement> {
//     const response = await api.get<Announcement>(
//       `/announcements/${id}/`
//     );

//     return response.data;
//   },
// };

// export default announcementService;

import api from "./api";

import type {
  Announcement,
  PaginatedAnnouncementResponse,
} from "../types/announcement";

const announcementService = {
  // Get all published announcements.
  getAllAnnouncements: async (): Promise<Announcement[]> => {
    const response = await api.get<
      Announcement[] | PaginatedAnnouncementResponse
    >("/announcements/");

    const data = response.data;

    // Django REST Framework pagination.
    if (!Array.isArray(data) && Array.isArray(data.results)) {
      return data.results;
    }

    // Non-paginated response.
    return data as Announcement[];
  },

  // Get the latest published announcements.
  getLatestAnnouncements: async (): Promise<Announcement[]> => {
    const response = await api.get<
      Announcement[] | PaginatedAnnouncementResponse
    >("/announcements/latest/");

    const data = response.data;

    if (!Array.isArray(data) && Array.isArray(data.results)) {
      return data.results;
    }

    return data as Announcement[];
  },

  // Get one announcement by its ID.
  getAnnouncement: async (id: number): Promise<Announcement> => {
    const response = await api.get<Announcement>(
      `/announcements/${id}/`
    );

    return response.data;
  },
};

export default announcementService;
