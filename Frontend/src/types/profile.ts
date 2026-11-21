
export interface PrivacySettings {
  profile_visibility: "public" | "private";
  email_visibility: "public" | "private";
  date_of_birth_visibility: "public" | "private";
  bio_visibility: "public" | "private";
}

export interface UserProfile {
  id: number;
  username: string;
  full_name: string;
  email: string;
  phone_number: string;
  country: string;
  date_of_birth: string | null;
  bio: string;
  profile_picture_url: string | null;
  role: "user" | "coordinator" | "admin";
  is_email_verified: boolean;
  account_status: "active" | "deactivated";
  account_created_at: string;
  privacy: PrivacySettings;

  // Skills and interests
  skills: string[];
  interests: string[];

  achievement_counts?: Record<string, number>;
  achievements?: unknown[];
}

export interface AccountInformation {
  username: string;
  email: string;
  is_email_verified: boolean;
  role: "user" | "coordinator" | "admin";
  account_status: "active" | "deactivated";
  account_created_at: string;
  last_login: string | null;
  pending_email: string | null;
}

export interface EmailChangeResponse {
  message: string;
  new_email?: string;
}

export interface MessageResponse {
  message: string;
  profile_picture_url?: string | null;
}
