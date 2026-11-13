export type Role = "student" | "coordinator" | "admin";

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
}

export interface Category {
  id: number;
  name: string;
  description: string;
  icon: string;
}

export type ActivityStatus =
  | "draft"
  | "published"
  | "registration_open"
  | "registration_closed"
  | "ongoing"
  | "completed"
  | "cancelled";

// export interface Activity {
//   id: number;
//   title: string;
//   description: string;
//   category_name: string;
//   venue: string;
//   date: string; // YYYY-MM-DD
//   start_time: string;
//   deadline: string;
//   max_participants: number;
//   registered_count: number;
//   banner: string | null;
//   status: ActivityStatus;
// }

// export interface Announcement {
//   id: number;
//   title: string;
//   description: string;
//   published_at: string;
// }

export interface Activity {
  id: number;
  title: string;
  description: string;
  category_name: string;
  venue: string;
  date: string; // YYYY-MM-DD
  start_time: string;
  deadline: string;
  max_participants: number;
  registered_count: number;
  banner: string | null;
  status: ActivityStatus;

  // optional extras used by the details page
  highlights?: string[];
  organizer?: string;
  format?: string;
  reward?: string;
}

export interface Announcement {
  id: number;
  title: string;
  description: string;
  published_at: string;

  // optional extras used by the bulletins section
  category?: string;
  status?: "deadline" | "ready" | "community";
  status_label?: string;
  issuer?: string;
  issuer_label?: string;
  highlight?: string;
  action_label?: string;
  action_url?: string;
}
// Shape of a paginated DRF response
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
