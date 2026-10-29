import type { Activity, Announcement, Category } from "../types";

// Sample data shown when the backend is not reachable yet. Delete once the API is live.
export const mockCategories: Category[] = [
  { id: 1, name: "Sports", description: "Futsal, cricket, athletics", icon: "⚽" },
  { id: 2, name: "Technology", description: "Hackathons and coding clubs", icon: "💻" },
  { id: 3, name: "Cultural", description: "Festivals, dance and drama", icon: "🎭" },
  { id: 4, name: "Music", description: "Bands, choir and open mics", icon: "🎸" },
  { id: 5, name: "Arts", description: "Painting, photography, design", icon: "🎨" },
  { id: 6, name: "Leadership", description: "Debates and student councils", icon: "🎤" },
  { id: 7, name: "Social Service", description: "Blood drives and clean-ups", icon: "🤝" },
  { id: 8, name: "Workshop", description: "Short hands-on skill sessions", icon: "🛠️" },
];

export const mockActivities: Activity[] = [
  {
    id: 1, title: "Inter-College Futsal Cup", description: "Five-a-side knockout tournament.",
    category_name: "Sports", venue: "College Ground", date: "2026-11-14", start_time: "09:00",
    deadline: "2026-11-08", max_participants: 80, registered_count: 62, banner: null, status: "registration_open",
  },
  {
    id: 2, title: "48-Hour Campus Hackathon", description: "Build something useful for the campus.",
    category_name: "Technology", venue: "Computer Lab 2", date: "2026-11-21", start_time: "10:00",
    deadline: "2026-11-15", max_participants: 60, registered_count: 60, banner: null, status: "registration_open",
  },
  {
    id: 3, title: "Cultural Night", description: "Dance, drama and food stalls.",
    category_name: "Cultural", venue: "Main Auditorium", date: "2026-12-02", start_time: "16:00",
    deadline: "2026-11-27", max_participants: 200, registered_count: 48, banner: null, status: "registration_open",
  },
];

export const mockAnnouncements: Announcement[] = [
  { id: 1, title: "Futsal Cup registrations close on 8 November", description: "Teams must submit a full roster of five players.", published_at: "2026-10-27" },
  { id: 2, title: "Photography Walk certificates are ready", description: "Download them from your student dashboard.", published_at: "2026-10-24" },
  { id: 3, title: "New: blood donation drive with the Red Cross", description: "Volunteers will receive a certificate.", published_at: "2026-10-20" },
];
