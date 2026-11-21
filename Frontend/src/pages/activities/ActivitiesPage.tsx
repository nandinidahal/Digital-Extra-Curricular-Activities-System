
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
  CalendarDays,
  MapPin,
  RefreshCw,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import announcementService from "../../services/announcementService";
import type { Announcement } from "../../types/announcement";

// Dashboard navigation
const navItems = [
  {
    label: "Overview",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Explore Activities",
    path: "/dashboard/activities",
    icon: ClipboardList,
  },
  {
    label: "Certificates",
    path: "/dashboard/achievements",
    icon: GraduationCap,
  },
  {
    label: "My Profile",
    path: "/dashboard/profile",
    icon: CircleUserRound,
  },
];

// Format activity date
const formatDate = (date: string | null | undefined): string => {
  if (!date) return "Date not announced";

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Date not announced";
  }

  return parsedDate.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

export default function ActivitiesPage() {
  const [activities, setActivities] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  // Initial API request
  useEffect(() => {
    let active = true;

    const loadActivities = async () => {
      try {
        const data = await announcementService.getAllAnnouncements();

        if (active) {
          setActivities(data);
          setError("");
        }
      } catch (err) {
        console.error("Failed to fetch activities:", err);

        if (active) {
          setError("Unable to load activities. Please try again.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadActivities();

    return () => {
      active = false;
    };
  }, []);

  // Refresh activities
  const fetchActivities = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await announcementService.getAllAnnouncements();

      setActivities(data);
    } catch (err) {
      console.error("Failed to fetch activities:", err);

      setError("Unable to load activities. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Get unique categories
  const categories = [
    "All",
    ...new Set(
      activities
        .map((activity) => activity.category?.name)
        .filter((name): name is string => Boolean(name))
    ),
  ];

  // Filter activities by category
  const filteredActivities = activities.filter((activity) => {
    return (
      selectedCategory === "All" ||
      activity.category?.name === selectedCategory
    );
  });

  return (
    <DashboardLayout
      role="user"
      title="Explore Activities"
      subtitle="Discover activities, events, workshops and opportunities."
      navItems={navItems}
    >
      <div className="min-h-screen bg-[#F8F7F3] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">

          {/* Page Header */}
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-[#315C4A]">
                Discover Opportunities
              </p>

              <h1 className="text-3xl font-bold text-[#17211B] sm:text-4xl">
                Explore Activities
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#657168] sm:text-base">
                Find opportunities to develop your skills, connect
                with others and build your extra-curricular portfolio.
              </p>
            </div>

            <button
              type="button"
              onClick={() => void fetchActivities()}
              disabled={loading}
              className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#315C4A] px-4 py-2.5 text-sm font-semibold text-[#315C4A] transition hover:bg-[#E8F1EC] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={loading ? "animate-spin" : ""}
              />
              Refresh
            </button>
          </div>

          {/* Statistics */}
          {!loading && !error && (
            <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
                <p className="text-sm text-gray-500">
                  Total Activities
                </p>

                <p className="mt-2 text-3xl font-bold text-[#315C4A]">
                  {activities.length.toString().padStart(2, "0")}
                </p>
              </div>

              <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
                <p className="text-sm text-gray-500">
                  Featured Activities
                </p>

                <p className="mt-2 text-3xl font-bold text-[#315C4A]">
                  {activities
                    .filter((activity) => activity.is_featured)
                    .length.toString()
                    .padStart(2, "0")}
                </p>
              </div>

              <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
                <p className="text-sm text-gray-500">
                  Important Activities
                </p>

                <p className="mt-2 text-3xl font-bold text-[#315C4A]">
                  {activities
                    .filter((activity) => activity.is_important)
                    .length.toString()
                    .padStart(2, "0")}
                </p>
              </div>
            </div>
          )}

          {/* Category Filter */}
          {!loading && !error && activities.length > 0 && (
            <div className="mb-7 rounded-xl border border-[#E1EAE4] bg-white p-4 sm:p-5">
              <h3 className="mb-4 text-sm font-semibold text-[#17211B]">
                Filter by Category
              </h3>

              <div className="flex flex-wrap gap-2">
                {categories.map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setSelectedCategory(category)}
                    className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                      selectedCategory === category
                        ? "bg-[#315C4A] text-white"
                        : "bg-[#F3F8F4] text-[#657168] hover:bg-[#E1EAE4]"
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="flex min-h-[300px] flex-col items-center justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#DCE6F2] border-t-[#315C4A]" />

              <p className="mt-4 text-sm text-[#657168]">
                Loading activities...
              </p>
            </div>
          )}

          {/* Error State */}
          {!loading && error && (
            <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-red-100 bg-white p-8 text-center">
              <div className="mb-4 rounded-full bg-red-50 p-4">
                <AlertCircle size={28} className="text-red-500" />
              </div>

              <h2 className="text-lg font-semibold text-[#17211B]">
                Something went wrong
              </h2>

              <p className="mt-2 max-w-md text-sm text-[#657168]">
                {error}
              </p>

              <button
                type="button"
                onClick={() => void fetchActivities()}
                className="mt-5 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#244637]"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && activities.length === 0 && (
            <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed border-[#DCE6F2] bg-white p-8 text-center">
              <ClipboardList
                size={42}
                className="text-[#315C4A]"
              />

              <h2 className="mt-4 text-lg font-semibold text-[#17211B]">
                No activities available
              </h2>

              <p className="mt-2 max-w-md text-sm text-[#657168]">
                There are currently no published activities.
                Please check again later.
              </p>
            </div>
          )}

          {/* Activity Results */}
          {!loading && !error && activities.length > 0 && (
            <>
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-[#657168]">
                  Showing{" "}
                  <span className="font-semibold text-[#17211B]">
                    {filteredActivities.length}
                  </span>{" "}
                  of{" "}
                  <span className="font-semibold text-[#17211B]">
                    {activities.length}
                  </span>{" "}
                  activities
                </p>
              </div>

              {filteredActivities.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#DCE6F2] bg-white py-14 text-center">
                  <h3 className="font-semibold text-[#17211B]">
                    No activities found in this category
                  </h3>

                  <p className="mt-2 text-sm text-[#657168]">
                    Try selecting another category.
                  </p>

                  <button
                    type="button"
                    onClick={() => setSelectedCategory("All")}
                    className="mt-4 text-sm font-semibold text-[#315C4A] hover:underline"
                  >
                    View All Activities
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredActivities.map((activity) => (
                    <article
                      key={activity.id}
                      className="group flex h-full flex-col overflow-hidden rounded-2xl border border-[#DCE6F2] bg-white shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-lg"
                    >
                      {/* Activity Image */}
                      <div className="relative h-52 overflow-hidden bg-[#E8F1EC]">
                        {activity.image_url ? (
                          <img
                            src={activity.image_url}
                            alt={
                              activity.activity_name || activity.title
                            }
                            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center">
                            <CalendarDays
                              size={42}
                              className="text-[#315C4A]"
                            />
                          </div>
                        )}

                        {activity.is_featured && (
                          <span className="absolute left-3 top-3 rounded-full bg-[#315C4A] px-3 py-1 text-xs font-semibold text-white">
                            Featured
                          </span>
                        )}

                        {activity.is_important && (
                          <span className="absolute right-3 top-3 rounded-full bg-[#D99A4E] px-3 py-1 text-xs font-semibold text-white">
                            Important
                          </span>
                        )}
                      </div>

                      {/* Activity Details */}
                      <div className="flex flex-1 flex-col p-5">
                        {activity.category?.name && (
                          <div className="mb-3">
                            <span className="inline-block rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-semibold text-[#315C4A]">
                              {activity.category.name}
                            </span>
                          </div>
                        )}

                        <h2 className="line-clamp-2 text-lg font-bold text-[#17211B] transition group-hover:text-[#315C4A]">
                          {activity.activity_name || activity.title}
                        </h2>

                        <p className="mt-3 line-clamp-3 flex-1 text-sm leading-6 text-[#657168]">
                          {activity.short_description ||
                            "Explore this activity and learn more about the opportunity."}
                        </p>

                        {/* Date */}
                        <div className="mt-4 flex items-center gap-2 text-sm text-[#657168]">
                          <CalendarDays
                            size={16}
                            className="shrink-0 text-[#315C4A]"
                          />

                          <span>
                            {formatDate(
                              activity.start_date || activity.event_date
                            )}
                          </span>
                        </div>

                        {/* Location */}
                        {activity.location && (
                          <div className="mt-2 flex items-center gap-2 text-sm text-[#657168]">
                            <MapPin
                              size={16}
                              className="shrink-0 text-[#315C4A]"
                            />

                            <span className="line-clamp-1">
                              {activity.location}
                            </span>
                          </div>
                        )}

                        {/* View Details */}
                        <Link
                          to={`/activities/${activity.id}`}
                          className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg bg-[#315C4A] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#244637]"
                        >
                          View Details

                          <ArrowRight
                            size={16}
                            className="transition group-hover:translate-x-1"
                          />
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
