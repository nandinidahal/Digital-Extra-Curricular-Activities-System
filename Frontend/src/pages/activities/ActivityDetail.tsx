
// import { useEffect, useState } from "react";
// import { Link, useParams } from "react-router-dom";
// import {
//   ArrowLeft,
//   CalendarDays,
//   MapPin,
//   Tag,
//   RefreshCw,
// } from "lucide-react";

// import announcementService from "../../services/announcementService";
// import type { Announcement } from "../../types/announcement";

// interface ActivityDetailData extends Announcement {
//   full_description?: string | null;
//   activity_type?: string | null;
//   country?: string | null;
//   keywords?: string[] | null;
// }

// const formatDate = (date: string | null | undefined) => {
//   if (!date) return "Date not announced";

//   const parsedDate = new Date(date);

//   if (Number.isNaN(parsedDate.getTime())) {
//     return "Date not announced";
//   }

//   return parsedDate.toLocaleDateString("en-GB", {
//     day: "2-digit",
//     month: "long",
//     year: "numeric",
//   });
// };

// export default function ActivityDetail() {
//   const { id } = useParams<{ id: string }>();

//   const [activity, setActivity] =
//     useState<ActivityDetailData | null>(null);

//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState("");

//   const fetchActivity = async () => {
//     if (!id) {
//       setError("Activity ID is missing.");
//       setLoading(false);
//       return;
//     }

//     try {
//       setLoading(true);
//       setError("");

//       const data =
//         await announcementService.getAnnouncementById(id);

//       setActivity(data);
//     } catch (err) {
//       console.error("Failed to fetch activity:", err);
//       setError("Unable to load activity details.");
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => {
//     let active = true;

//     const loadActivity = async () => {
//       if (!id) {
//         setError("Activity ID is missing.");
//         setLoading(false);
//         return;
//       }

//       try {
//         setLoading(true);
//         setError("");

//         const data =
//           await announcementService.getAnnouncementById(id);

//         if (active) {
//           setActivity(data);
//         }
//       } catch (err) {
//         console.error("Failed to fetch activity:", err);

//         if (active) {
//           setError("Unable to load activity details.");
//         }
//       } finally {
//         if (active) {
//           setLoading(false);
//         }
//       }
//     };

//     void loadActivity();

//     return () => {
//       active = false;
//     };
//   }, [id]);

//   if (loading) {
//     return (
//       <div className="grid min-h-screen place-items-center">
//         <div className="text-center">
//           <RefreshCw
//             size={32}
//             className="mx-auto animate-spin text-[#315C4A]"
//           />
//           <p className="mt-3 text-gray-500">
//             Loading activity details...
//           </p>
//         </div>
//       </div>
//     );
//   }

//   if (error || !activity) {
//     return (
//       <div className="grid min-h-screen place-items-center px-4">
//         <div className="text-center">
//           <h2 className="text-xl font-bold text-gray-800">
//             Activity Not Available
//           </h2>

//           <p className="mt-2 text-sm text-gray-500">
//             {error || "This activity could not be found."}
//           </p>

//           <button
//             type="button"
//             onClick={() => void fetchActivity()}
//             className="mt-5 rounded-lg bg-[#315C4A] px-5 py-2 text-white"
//           >
//             Try Again
//           </button>

//           <div>
//             <Link
//               to="/dashboard/activities"
//               className="mt-4 inline-block text-sm text-[#315C4A] hover:underline"
//             >
//               Back to Activities
//             </Link>
//           </div>
//         </div>
//       </div>
//     );
//   }

//   return (
//     <div className="min-h-screen bg-[#F8F7F3] px-4 py-8 sm:px-6">
//       <div className="mx-auto max-w-4xl">

//         {/* Back Button */}
//         <Link
//           to="/dashboard/activities"
//           className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
//         >
//           <ArrowLeft size={17} />
//           Back to Activities
//         </Link>

//         {/* Activity Card */}
//         <article className="overflow-hidden rounded-2xl border border-[#E1EAE4] bg-white shadow-sm">

//           {/* Activity Image */}
//           {activity.image_url ? (
//             <img
//               src={activity.image_url}
//               alt={activity.activity_name || activity.title}
//               className="h-64 w-full object-cover sm:h-80"
//             />
//           ) : (
//             <div className="grid h-64 place-items-center bg-[#E8F1EC]">
//               <CalendarDays
//                 size={60}
//                 className="text-[#315C4A]"
//               />
//             </div>
//           )}

//           <div className="p-6 sm:p-9">

//             {/* Labels */}
//             <div className="mb-4 flex flex-wrap gap-2">
//               {activity.category?.name && (
//                 <span className="rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-semibold text-[#315C4A]">
//                   {activity.category.name}
//                 </span>
//               )}

//               {activity.is_featured && (
//                 <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
//                   Featured
//                 </span>
//               )}

//               {activity.is_important && (
//                 <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-600">
//                   Important
//                 </span>
//               )}
//             </div>

//             {/* Title */}
//             <h1 className="text-2xl font-bold text-gray-800 sm:text-3xl">
//               {activity.activity_name || activity.title}
//             </h1>

//             {/* Short Description */}
//             {activity.short_description && (
//               <p className="mt-4 text-base leading-7 text-gray-500">
//                 {activity.short_description}
//               </p>
//             )}

//             {/* Activity Information */}
//             <div className="mt-7 grid gap-4 rounded-xl bg-[#F8FAF8] p-5 sm:grid-cols-2">

//               <div className="flex items-start gap-3">
//                 <CalendarDays
//                   size={20}
//                   className="mt-1 shrink-0 text-[#315C4A]"
//                 />
//                 <div>
//                   <p className="text-xs text-gray-500">
//                     Start Date
//                   </p>
//                   <p className="mt-1 text-sm font-semibold text-gray-800">
//                     {formatDate(
//                       activity.start_date || activity.event_date
//                     )}
//                   </p>
//                 </div>
//               </div>

//               {activity.location && (
//                 <div className="flex items-start gap-3">
//                   <MapPin
//                     size={20}
//                     className="mt-1 shrink-0 text-[#315C4A]"
//                   />
//                   <div>
//                     <p className="text-xs text-gray-500">
//                       Location
//                     </p>
//                     <p className="mt-1 text-sm font-semibold text-gray-800">
//                       {activity.location}
//                     </p>
//                   </div>
//                 </div>
//               )}

//               {activity.activity_type && (
//                 <div className="flex items-start gap-3">
//                   <Tag
//                     size={20}
//                     className="mt-1 shrink-0 text-[#315C4A]"
//                   />
//                   <div>
//                     <p className="text-xs text-gray-500">
//                       Activity Type
//                     </p>
//                     <p className="mt-1 text-sm font-semibold text-gray-800">
//                       {activity.activity_type}
//                     </p>
//                   </div>
//                 </div>
//               )}

//               {activity.country && (
//                 <div>
//                   <p className="text-xs text-gray-500">
//                     Country
//                   </p>
//                   <p className="mt-1 text-sm font-semibold text-gray-800">
//                     {activity.country}
//                   </p>
//                 </div>
//               )}
//             </div>

//             {/* Full Description */}
//             <section className="mt-8">
//               <h2 className="text-xl font-bold text-gray-800">
//                 About This Activity
//               </h2>

//               <div className="mt-3 whitespace-pre-line text-sm leading-7 text-gray-600">
//                 {activity.full_description ||
//                   activity.short_description ||
//                   "No additional description available."}
//               </div>
//             </section>

//             {/* Keywords */}
//             {activity.keywords &&
//               activity.keywords.length > 0 && (
//                 <section className="mt-7">
//                   <h2 className="font-semibold text-gray-800">
//                     Keywords
//                   </h2>

//                   <div className="mt-3 flex flex-wrap gap-2">
//                     {activity.keywords.map((keyword, index) => (
//                       <span
//                         key={`${keyword}-${index}`}
//                         className="rounded-full bg-[#E8F1EC] px-3 py-1 text-xs text-[#315C4A]"
//                       >
//                         {keyword}
//                       </span>
//                     ))}
//                   </div>
//                 </section>
//               )}

//           </div>
//         </article>
//       </div>
//     </div>
//   );
// }

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ArrowLeft,
  CalendarDays,
  MapPin,
  Globe,
  Tag,
  Download,
  Clock,
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import announcementService from "../../services/announcementService";

import type { Announcement } from "../../types/announcement";

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

const formatDate = (date?: string | null) => {
  if (!date) return "Not announced";

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Not announced";
  }

  return parsedDate.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
};

const formatActivityType = (type?: string) => {
  if (!type) return "Not specified";

  return type.charAt(0).toUpperCase() + type.slice(1);
};

export default function ActivityDetail() {
  const { id } = useParams<{ id: string }>();

  const [activity, setActivity] = useState<Announcement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    const fetchActivity = async () => {
      if (!id || !/^[1-9]\d*$/.test(id)) {
        setError("Invalid activity ID.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const data = await announcementService.getAnnouncement(
          Number(id)
        );

        if (active) {
          setActivity(data);
        }
      } catch (err) {
        console.error("Failed to fetch activity:", err);

        if (active) {
          setError(
            "Unable to load this activity. It may have been removed or is not available."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void fetchActivity();

    return () => {
      active = false;
    };
  }, [id]);

  return (
    <DashboardLayout
      role="user"
      title="Activity Details"
      subtitle="View complete information about this activity."
      navItems={navItems}
    >
      {/* Back Button */}
      <div className="mb-6">
        <Link
          to="/dashboard/activities"
          className="inline-flex items-center gap-2 text-sm font-medium text-[#315C4A] hover:underline"
        >
          <ArrowLeft size={16} />
          Back to Activities
        </Link>
      </div>

      {/* Loading */}
      {loading && (
        <div className="rounded-xl border border-[#E1EAE4] bg-white py-20 text-center">
          <div className="mx-auto h-9 w-9 animate-spin rounded-full border-2 border-[#315C4A] border-t-transparent" />

          <p className="mt-4 text-sm text-gray-500">
            Loading activity details...
          </p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-xl border border-red-100 bg-white p-8 text-center">
          <CalendarDays
            size={42}
            className="mx-auto text-gray-400"
          />

          <h2 className="mt-4 text-lg font-bold text-gray-800">
            Activity Not Available
          </h2>

          <p className="mt-2 text-sm text-red-600">
            {error}
          </p>

          <Link
            to="/dashboard/activities"
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#244738]"
          >
            <ArrowLeft size={16} />
            Back to Activities
          </Link>
        </div>
      )}

      {/* Activity Details */}
      {!loading && !error && activity && (
        <article className="overflow-hidden rounded-xl border border-[#E1EAE4] bg-white">

          {/* Cover Image */}
          {activity.image_url ? (
            <img
              src={activity.image_url}
              alt={activity.activity_name || activity.title}
              className="h-64 w-full object-cover sm:h-80"
            />
          ) : (
            <div className="grid h-64 w-full place-items-center bg-[#E8F1EC]">
              <CalendarDays
                size={64}
                className="text-[#315C4A]"
              />
            </div>
          )}

          <div className="p-5 sm:p-8">

            {/* Badges */}
            <div className="flex flex-wrap gap-2">
              {activity.category?.name && (
                <span className="rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-semibold text-[#315C4A]">
                  {activity.category.name}
                </span>
              )}

              {activity.is_featured && (
                <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                  Featured
                </span>
              )}

              {activity.is_important && (
                <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-600">
                  Important
                </span>
              )}
            </div>

            {/* Title */}
            <h1 className="mt-4 text-2xl font-bold text-gray-900 sm:text-3xl">
              {activity.activity_name || activity.title}
            </h1>

            {/* Short Description */}
            <p className="mt-3 text-base leading-7 text-gray-600">
              {activity.short_description}
            </p>

            {/* Information Grid */}
            <div className="mt-6 grid grid-cols-1 gap-4 rounded-xl bg-[#F5F8F6] p-5 sm:grid-cols-2">

              <div className="flex items-start gap-3">
                <CalendarDays
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    Start Date
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {formatDate(activity.start_date || activity.event_date)}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <CalendarDays
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    End Date
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {formatDate(activity.end_date)}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <MapPin
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    Location
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {activity.location || "Not specified"}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Globe
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    Country
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {activity.country || "Not specified"}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Tag
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    Activity Type
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {formatActivityType(activity.activity_type)}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Clock
                  size={20}
                  className="mt-0.5 shrink-0 text-[#315C4A]"
                />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    Registration Deadline
                  </p>
                  <p className="mt-1 text-sm font-semibold text-gray-800">
                    {formatDate(activity.deadline)}
                  </p>
                </div>
              </div>
            </div>

            {/* Full Description */}
            <section className="mt-8">
              <h2 className="text-xl font-bold text-gray-800">
                About This Activity
              </h2>

              <div className="mt-3 whitespace-pre-line text-sm leading-7 text-gray-600">
                {activity.full_description ||
                  activity.short_description ||
                  "No additional description is available."}
              </div>
            </section>

            {/* Keywords */}
            {activity.keywords && (
              <section className="mt-8">
                <h2 className="text-lg font-bold text-gray-800">
                  Keywords
                </h2>

                <div className="mt-3 flex flex-wrap gap-2">
                  {activity.keywords
                    .split(",")
                    .map((keyword) => keyword.trim())
                    .filter(Boolean)
                    .map((keyword) => (
                      <span
                        key={keyword}
                        className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
                      >
                        {keyword}
                      </span>
                    ))}
                </div>
              </section>
            )}

            {/* Attachment */}
            {activity.attachment?.download_url && (
              <section className="mt-8 rounded-xl border border-[#E1EAE4] p-5">
                <h2 className="font-bold text-gray-800">
                  Activity Attachment
                </h2>

                <p className="mt-1 text-sm text-gray-500">
                  {activity.attachment.name}
                </p>

                <a
                  href={activity.attachment.download_url}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#244738]"
                >
                  <Download size={16} />
                  Download Attachment
                </a>
              </section>
            )}

            {/* Back */}
            <div className="mt-8 border-t border-gray-100 pt-5">
              <Link
                to="/dashboard/activities"
                className="inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
              >
                <ArrowLeft size={16} />
                Back to All Activities
              </Link>
            </div>
          </div>
        </article>
      )}
    </DashboardLayout>
  );
}
