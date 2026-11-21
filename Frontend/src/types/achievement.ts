
export type AchievementVisibility = "public" | "private";

export interface AchievementCategory {
  id: number;
  name: string;
  slug: string;
  description: string;
}

export interface AchievementDocument {
  id: number;
  document_type: "certificate" | "supporting";
  document_name: string;
  original_filename: string;
  content_type: string;
  size: number;
  uploaded_at: string;
  download_url: string;
}

export interface AchievementOwner {
  id: number;
  full_name: string;
  username: string;
}

export interface Achievement {
  id: number;
  title: string;
  category: AchievementCategory;
  description: string;
  issuing_organization: string;
  achievement_date: string;
  certificate_number: string;
  location: string;
  visibility?: AchievementVisibility;
  documents: AchievementDocument[];
  owner: AchievementOwner;
  created_at: string;
  updated_at?: string;
}

export interface AchievementFormData {
  title: string;
  category: number;
  description: string;
  issuing_organization: string;
  achievement_date: string;
  certificate_number: string;
  location: string;
  visibility: AchievementVisibility;
  certificate?: File | null;
  supporting_documents: File[];
  remove_document_ids: number[];
}

export interface PaginatedResponse<T> {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
}
