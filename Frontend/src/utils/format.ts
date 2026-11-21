// import type { ActivityStatus } from "../types";

// export const formatDate = (iso: string) =>
//   new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

// export const dashboardPath = (role: string) => `/${role}/dashboard`;

// export const statusLabel: Record<ActivityStatus, string> = {
//   draft: "Draft",
//   published: "Published",
//   registration_open: "Registration open",
//   registration_closed: "Registration closed",
//   ongoing: "Ongoing",
//   completed: "Completed",
//   cancelled: "Cancelled",
// };

import type { ActivityStatus } from "../types";

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

export const dashboardPath = (role: string): string => {
  switch (role) {
    case "user":
      return "/dashboard";

    case "coordinator":
      return "/coordinator/dashboard";

    case "admin":
      return "/admin/dashboard";

    default:
      return "/login";
  }
};

export const statusLabel: Record<ActivityStatus, string> = {
  draft: "Draft",
  published: "Published",
  registration_open: "Registration open",
  registration_closed: "Registration closed",
  ongoing: "Ongoing",
  completed: "Completed",
  cancelled: "Cancelled",
};
