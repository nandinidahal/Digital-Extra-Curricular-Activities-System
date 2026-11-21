
export interface AnnouncementCategory {
  id?: number;
  name: string;
  slug?: string;
  description?: string;
}

export interface AnnouncementAuthor {
  id: number;
  username: string;
  full_name: string;
}

export interface AnnouncementAttachment {
  name: string;
  size: number | null;
  download_url: string;
}

export interface Announcement {
  id: number;
  title: string;
  short_description: string;
  full_description?: string;

  activity_name: string;
  activity_type?: "physical" | "online" | "hybrid";

  category: AnnouncementCategory;
  author?: AnnouncementAuthor;

  image_url: string | null;

  country?: string;
  location: string;

  start_date: string | null;
  event_date?: string | null;
  end_date?: string | null;
  deadline?: string | null;

  keywords?: string;

  published_at?: string | null;
  created_at?: string;
  updated_at?: string;

  is_featured: boolean;
  is_important: boolean;

  bookmark_count?: number;
  is_bookmarked?: boolean;

  state?: string;
  is_owner?: boolean;
  can_edit?: boolean;

  expires_at?: string | null;

  attachment?: AnnouncementAttachment | null;

  share_id?: string;
  share_url?: string;
}

export interface PaginatedAnnouncementResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Announcement[];
}
