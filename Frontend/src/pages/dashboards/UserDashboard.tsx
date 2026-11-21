
// import { useEffect, useState } from "react";
// import { Link } from "react-router-dom";
// import {
//   LayoutDashboard,
//   ClipboardList,
//   GraduationCap,
//   CircleUserRound,
//   CalendarCheck,
//   CheckCircle,
//   Award,
//   Trophy,
//   CalendarDays,
//   MapPin,
//   RefreshCw,
// } from "lucide-react";

// import DashboardLayout from "../../components/dashboard/DashboardLayout";
// import profileService from "../../services/profileService";
// import announcementService from "../../services/announcementService";

// import type { UserProfile } from "../../types/profile";
// import type { Announcement } from "../../types/announcement";

// const navItems = [
//   {
//     label: "Overview",
//     path: "/dashboard",
//     icon: LayoutDashboard,
//   },
//   {
//     label: "Explore Activities",
//     path: "/dashboard/activities",
//     icon: ClipboardList,
//   },
//   {
//     label: "Certificates",
//     path: "/dashboard/achievements",
//     icon: GraduationCap,
//   },
//   {
//     label: "My Profile",
//     path: "/dashboard/profile",
//     icon: CircleUserRound,
//   },
// ];

// // These statistics are still sample values.
// // The supplied backend does not provide student registration statistics.
// const stats = [
//   {
//     label: "Registered Activities",
//     value: "04",
//     icon: CalendarCheck,
//   },
//   {
//     label: "Completed Activities",
//     value: "02",
//     icon: CheckCircle,
//   },
//   {
//     label: "Certificates Earned",
//     value: "02",
//     icon: Award,
//   },
//   {
//     label: "Achievements",
//     value: "03",
//     icon: Trophy,
//   },
// ];

// const formatDate = (date: string | null) => {
//   if (!date) return "Date not announced";

//   const parsedDate = new Date(date);

//   if (Number.isNaN(parsedDate.getTime())) {
//     return "Date not announced";
//   }

//   return parsedDate.toLocaleDateString("en-GB", {
//     day: "2-digit",
//     month: "short",
//     year: "numeric",
//   });
// };

// export default function UserDashboard() {
//   const [profile, setProfile] = useState<UserProfile | null>(null);
//   const [profileLoading, setProfileLoading] = useState(true);
//   const [profileError, setProfileError] = useState("");

//   const [activities, setActivities] = useState<Announcement[]>([]);
//   const [activitiesLoading, setActivitiesLoading] = useState(true);
//   const [activitiesError, setActivitiesError] = useState("");

//   // Fetch profile
//   useEffect(() => {
//     let active = true;

//     const fetchProfile = async () => {
//       try {
//         const data = await profileService.getMyProfile();

//         if (active) {
//           setProfile(data);
//           setProfileError("");
//         }
//       } catch (error) {
//         console.error("Failed to load profile:", error);

//         if (active) {
//           setProfileError("Unable to load your profile.");
//         }
//       } finally {
//         if (active) {
//           setProfileLoading(false);
//         }
//       }
//     };

//     void fetchProfile();

//     return () => {
//       active = false;
//     };
//   }, []);

//   // Fetch latest published activities
//   useEffect(() => {
//     let active = true;

//     const fetchActivities = async () => {
//       try {
//         setActivitiesLoading(true);
//         setActivitiesError("");

//         const data =
//           await announcementService.getLatestAnnouncements();

//         if (active) {
//           setActivities(data.slice(0, 4));
//         }
//       } catch (error) {
//         console.error("Failed to load activities:", error);

//         if (active) {
//           setActivitiesError(
//             "Unable to load activities. Please try again."
//           );
//         }
//       } finally {
//         if (active) {
//           setActivitiesLoading(false);
//         }
//       }
//     };

//     void fetchActivities();

//     return () => {
//       active = false;
//     };
//   }, []);

//   const handleRetryActivities = async () => {
//     try {
//       setActivitiesLoading(true);
//       setActivitiesError("");

//       const data =
//         await announcementService.getLatestAnnouncements();

//       setActivities(data.slice(0, 4));
//     } catch (error) {
//       console.error("Failed to reload activities:", error);
//       setActivitiesError(
//         "Unable to load activities. Please try again."
//       );
//     } finally {
//       setActivitiesLoading(false);
//     }
//   };

//   const fullName =
//     profile?.full_name || profile?.username || "Your Name";

//   const roleLabel =
//     profile?.role === "user"
//       ? "Student"
//       : profile?.role === "coordinator"
//         ? "Coordinator"
//         : profile?.role === "admin"
//           ? "Administrator"
//           : "User";

//   const initials = fullName
//     .split(" ")
//     .filter(Boolean)
//     .map((word) => word[0])
//     .join("")
//     .slice(0, 2)
//     .toUpperCase();

//   return (
//     <DashboardLayout
//       role="user"
//       title="My Dashboard"
//       subtitle="Welcome back! Here is your activity overview."
//       navItems={navItems}
//     >
//       {/* Welcome Section */}
//       <section className="rounded-2xl bg-[#315C4A] p-6 text-white sm:p-8">
//         <p className="text-sm text-white/75">
//           Welcome back,
//         </p>

//         <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
//           {profileLoading ? "Loading..." : fullName}
//         </h2>

//         <p className="mt-2 max-w-xl text-sm leading-6 text-white/80">
//           Explore activities, develop your skills, participate in
//           events and build your extra-curricular portfolio.
//         </p>

//         <Link
//           to="/activities"
//           className="mt-5 inline-block rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-[#315C4A] hover:bg-gray-100"
//         >
//           Explore Activities
//         </Link>
//       </section>

//       {/* Statistics */}
//       <section className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
//         {stats.map((stat) => {
//           const Icon = stat.icon;

//           return (
//             <div
//               key={stat.label}
//               className="rounded-xl border border-[#E1EAE4] bg-white p-5"
//             >
//               <div className="flex items-center justify-between">
//                 <p className="text-sm text-gray-500">
//                   {stat.label}
//                 </p>

//                 <Icon
//                   size={22}
//                   className="text-[#315C4A]"
//                 />
//               </div>

//               <p className="mt-3 text-3xl font-bold">
//                 {stat.value}
//               </p>
//             </div>
//           );
//         })}
//       </section>

//       <div className="mt-7 grid grid-cols-1 gap-6 xl:grid-cols-3">
//         {/* Dynamic Latest Activities */}
//         <section className="rounded-xl border border-[#E1EAE4] bg-white p-5 xl:col-span-2">
//           <div className="flex items-center justify-between gap-3">
//             <div>
//               <h3 className="font-bold">
//                 Latest Activities
//               </h3>

//               <p className="mt-1 text-sm text-gray-500">
//                 Discover the latest published activities and events.
//               </p>
//             </div>

//             <Link
//               to="/dashboard/activities"
//               className="shrink-0 text-sm font-semibold text-[#315C4A] hover:underline"
//             >
//               View all
//             </Link>
//           </div>

//           <div className="mt-5 space-y-3">
//             {/* Loading */}
//             {activitiesLoading && (
//               <div className="py-10 text-center">
//                 <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-[#315C4A] border-t-transparent" />

//                 <p className="mt-3 text-sm text-gray-500">
//                   Loading activities...
//                 </p>
//               </div>
//             )}

//             {/* Error */}
//             {!activitiesLoading && activitiesError && (
//               <div className="rounded-lg bg-red-50 p-5 text-center">
//                 <p className="text-sm text-red-600">
//                   {activitiesError}
//                 </p>

//                 <button
//                   type="button"
//                   onClick={handleRetryActivities}
//                   className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
//                 >
//                   <RefreshCw size={15} />
//                   Try again
//                 </button>
//               </div>
//             )}

//             {/* Empty State */}
//             {!activitiesLoading &&
//               !activitiesError &&
//               activities.length === 0 && (
//                 <div className="rounded-lg border border-dashed border-gray-200 py-10 text-center">
//                   <CalendarDays
//                     size={32}
//                     className="mx-auto text-gray-400"
//                   />

//                   <h4 className="mt-3 font-semibold text-gray-700">
//                     No activities available
//                   </h4>

//                   <p className="mt-1 text-sm text-gray-500">
//                     New activities will appear here when published.
//                   </p>

//                   <Link
//                     to="/activities"
//                     className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//                   >
//                     Explore activities
//                   </Link>
//                 </div>
//               )}

//             {/* Activity List */}
//             {!activitiesLoading &&
//               !activitiesError &&
//               activities.map((activity) => (
//                 <div
//                   key={activity.id}
//                   className="rounded-lg border border-gray-100 p-4 transition hover:border-[#B9D0C2] hover:bg-[#F8FBF9]"
//                 >
//                   <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
//                     <div className="min-w-0 flex-1">
//                       <div className="flex flex-wrap items-center gap-2">
//                         <h4 className="font-semibold text-gray-800">
//                           {activity.activity_name ||
//                             activity.title}
//                         </h4>

//                         {activity.is_featured && (
//                           <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
//                             Featured
//                           </span>
//                         )}

//                         {activity.is_important && (
//                           <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-600">
//                             Important
//                           </span>
//                         )}
//                       </div>

//                       <p className="mt-2 line-clamp-2 text-sm leading-6 text-gray-500">
//                         {activity.short_description ||
//                           "View details to learn more about this activity."}
//                       </p>

//                       <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-gray-500">
//                         {activity.category?.name && (
//                           <span className="rounded-full bg-[#E8F1EC] px-3 py-1 font-medium text-[#315C4A]">
//                             {activity.category.name}
//                           </span>
//                         )}

//                         <span className="inline-flex items-center gap-1">
//                           <CalendarDays size={14} />
//                           {formatDate(
//                             activity.start_date ||
//                               activity.event_date
//                           )}
//                         </span>

//                         {activity.location && (
//                           <span className="inline-flex items-center gap-1">
//                             <MapPin size={14} />
//                             {activity.location}
//                           </span>
//                         )}
//                       </div>
//                     </div>

//                     <Link
//                       to={`/activities/${activity.id}`}
//                       className="w-fit shrink-0 text-sm font-semibold text-[#315C4A] hover:underline"
//                     >
//                       View Details →
//                     </Link>
//                   </div>
//                 </div>
//               ))}
//           </div>
//         </section>

//         {/* Dynamic Profile Summary */}
//         <section className="rounded-xl border border-[#E1EAE4] bg-white p-5">
//           <div className="flex items-center justify-between">
//             <h3 className="font-bold">
//               My Profile
//             </h3>

//             <Link
//               to="/dashboard/profile/edit"
//               className="text-sm font-semibold text-[#315C4A] hover:underline"
//             >
//               Edit
//             </Link>
//           </div>

//           {profileLoading ? (
//             <div className="mt-8 py-8 text-center text-sm text-gray-500">
//               Loading your profile...
//             </div>
//           ) : profileError ? (
//             <div className="mt-8 text-center">
//               <p className="text-sm text-red-500">
//                 {profileError}
//               </p>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//               >
//                 Open Profile
//               </Link>
//             </div>
//           ) : profile ? (
//             <>
//               {/* Profile Picture and Name */}
//               <div className="mt-5 flex flex-col items-center text-center">
//                 {profile.profile_picture_url ? (
//                   <img
//                     src={profile.profile_picture_url}
//                     alt={fullName}
//                     className="h-20 w-20 rounded-full border-2 border-[#E1EAE4] object-cover"
//                   />
//                 ) : (
//                   <div className="grid h-20 w-20 place-items-center rounded-full bg-[#E8F1EC] text-2xl font-bold text-[#315C4A]">
//                     {initials || "U"}
//                   </div>
//                 )}

//                 <h4 className="mt-3 font-bold">
//                   {fullName}
//                 </h4>

//                 <p className="text-sm text-gray-500">
//                   {roleLabel}
//                 </p>

//                 <p className="mt-1 text-xs text-gray-400">
//                   @{profile.username}
//                 </p>
//               </div>

//               {/* Profile Information */}
//               <div className="mt-5 space-y-4 border-t border-gray-100 pt-4 text-sm">
//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Email
//                   </p>

//                   <p className="mt-1 break-all font-medium">
//                     {profile.email || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Phone Number
//                   </p>

//                   <p className="mt-1 font-medium">
//                     {profile.phone_number || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Country
//                   </p>

//                   <p className="mt-1 font-medium">
//                     {profile.country || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Bio
//                   </p>

//                   <p className="mt-1 break-words text-gray-600">
//                     {profile.bio ||
//                       "Add a short introduction about yourself."}
//                   </p>
//                 </div>
//               </div>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-5 block rounded-lg border border-[#315C4A] py-2.5 text-center text-sm font-semibold text-[#315C4A] hover:bg-[#E8F1EC]"
//               >
//                 View Full Profile
//               </Link>
//             </>
//           ) : (
//             <div className="mt-6 text-center">
//               <p className="text-sm text-gray-500">
//                 Profile information is not available.
//               </p>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//               >
//                 Open Profile
//               </Link>
//             </div>
//           )}
//         </section>
//       </div>

//       {/* Skills and Interests */}
//       <section className="mt-6 rounded-xl border border-[#E1EAE4] bg-white p-5">
//         <h3 className="font-bold">
//           My Skills & Interests
//         </h3>

//         <p className="mt-1 text-sm text-gray-500">
//           Add your interests and skills to improve your profile.
//         </p>

//         <p className="mt-4 text-sm text-gray-500">
//           Visit your profile to manage your personal information.
//         </p>

//         <Link
//           to="/dashboard/profile"
//           className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//         >
//           Manage Profile →
//         </Link>
//       </section>
//     </DashboardLayout>
//   );
// }
 

// 4 part 

// import { useCallback, useEffect, useState } from "react";
// import { Link } from "react-router-dom";
// import {
//   LayoutDashboard,
//   ClipboardList,
//   GraduationCap,
//   CircleUserRound,
//   CalendarCheck,
//   CheckCircle,
//   Award,
//   Trophy,
//   CalendarDays,
//   MapPin,
//   RefreshCw,
// } from "lucide-react";

// import DashboardLayout from "../../components/dashboard/DashboardLayout";
// import profileService from "../../services/profileService";
// import announcementService from "../../services/announcementService";

// import type { UserProfile } from "../../types/profile";
// import type { Announcement } from "../../types/announcement";

// const navItems = [
//   {
//     label: "Overview",
//     path: "/dashboard",
//     icon: LayoutDashboard,
//   },
//   {
//     label: "Explore Activities",
//     path: "/dashboard/activities",
//     icon: ClipboardList,
//   },
//   {
//     label: "Certificates",
//     path: "/dashboard/achievements",
//     icon: GraduationCap,
//   },
//   {
//     label: "My Profile",
//     path: "/dashboard/profile",
//     icon: CircleUserRound,
//   },
// ];

// // Fixed: accepts string, null, or undefined.
// const formatDate = (date: string | null | undefined): string => {
//   if (!date) return "Date not announced";

//   const parsedDate = new Date(date);

//   if (Number.isNaN(parsedDate.getTime())) {
//     return "Date not announced";
//   }

//   return parsedDate.toLocaleDateString("en-GB", {
//     day: "2-digit",
//     month: "short",
//     year: "numeric",
//   });
// };

// export default function UserDashboard() {
//   // Profile states
//   const [profile, setProfile] = useState<UserProfile | null>(null);
//   const [profileLoading, setProfileLoading] = useState(true);
//   const [profileError, setProfileError] = useState("");

//   // Activity states
//   const [activities, setActivities] = useState<Announcement[]>([]);
//   const [activitiesLoading, setActivitiesLoading] = useState(true);
//   const [activitiesError, setActivitiesError] = useState("");

//   // Fetch logged-in user's profile
//   useEffect(() => {
//     let active = true;

//     const fetchProfile = async () => {
//       try {
//         const data = await profileService.getMyProfile();

//         if (active) {
//           setProfile(data);
//           setProfileError("");
//         }
//       } catch (error) {
//         console.error("Failed to load profile:", error);

//         if (active) {
//           setProfileError("Unable to load your profile.");
//         }
//       } finally {
//         if (active) {
//           setProfileLoading(false);
//         }
//       }
//     };

//     void fetchProfile();

//     return () => {
//       active = false;
//     };
//   }, []);

//   // Fetch activities when refreshing or retrying
//   const fetchActivities = useCallback(async () => {
//     try {
//       setActivitiesLoading(true);
//       setActivitiesError("");

//       const data = await announcementService.getAllAnnouncements();

//       setActivities(data);
//     } catch (error) {
//       console.error("Failed to load activities:", error);

//       setActivitiesError(
//         "Unable to load activities. Please try again."
//       );
//     } finally {
//       setActivitiesLoading(false);
//     }
//   }, []);

//   // Initial activities request
//   useEffect(() => {
//     let active = true;

//     const loadActivities = async () => {
//       try {
//         const data = await announcementService.getAllAnnouncements();

//         if (active) {
//           setActivities(data);
//           setActivitiesError("");
//         }
//       } catch (error) {
//         console.error("Failed to load activities:", error);

//         if (active) {
//           setActivitiesError(
//             "Unable to load activities. Please try again."
//           );
//         }
//       } finally {
//         if (active) {
//           setActivitiesLoading(false);
//         }
//       }
//     };

//     void loadActivities();

//     return () => {
//       active = false;
//     };
//   }, []);

//   // Profile information
//   const fullName =
//     profile?.full_name || profile?.username || "Your Name";

//   const roleLabel =
//     profile?.role === "user"
//       ? "Student"
//       : profile?.role === "coordinator"
//         ? "Coordinator"
//         : profile?.role === "admin"
//           ? "Administrator"
//           : "User";

//   const initials = fullName
//     .split(" ")
//     .filter(Boolean)
//     .map((word) => word[0])
//     .join("")
//     .slice(0, 2)
//     .toUpperCase();

//   // Calculate upcoming activities
//   const today = new Date();
//   today.setHours(0, 0, 0, 0);

//   const upcomingActivities = activities.filter((activity) => {
//     const date = activity.start_date || activity.event_date;

//     if (!date) return false;

//     const activityDate = new Date(date);

//     return (
//       !Number.isNaN(activityDate.getTime()) &&
//       activityDate >= today
//     );
//   });

//   // Dynamic dashboard statistics
//   const stats = [
//     {
//       label: "Published Activities",
//       value: activities.length.toString().padStart(2, "0"),
//       icon: CalendarCheck,
//     },
//     {
//       label: "Upcoming Activities",
//       value: upcomingActivities.length.toString().padStart(2, "0"),
//       icon: CheckCircle,
//     },
//     {
//       label: "Featured Activities",
//       value: activities
//         .filter((activity) => activity.is_featured)
//         .length.toString()
//         .padStart(2, "0"),
//       icon: Award,
//     },
//     {
//       label: "Important Activities",
//       value: activities
//         .filter((activity) => activity.is_important)
//         .length.toString()
//         .padStart(2, "0"),
//       icon: Trophy,
//     },
//   ];

//   // Show the latest four activities
//   const latestActivities = activities.slice(0, 4);

//   return (
//     <DashboardLayout
//       role="user"
//       title="My Dashboard"
//       subtitle="Welcome back! Here is your activity overview."
//       navItems={navItems}
//     >
//       {/* Welcome Section */}
//       <section className="rounded-2xl bg-[#315C4A] p-6 text-white sm:p-8">
//         <p className="text-sm text-white/75">
//           Welcome back,
//         </p>

//         <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
//           {profileLoading ? "Loading..." : fullName}
//         </h2>

//         <p className="mt-2 max-w-xl text-sm leading-6 text-white/80">
//           Explore activities, develop your skills, participate in events
//           and build your extra-curricular portfolio.
//         </p>

//         <Link
//           to="/activities"
//           className="mt-5 inline-block rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-[#315C4A] hover:bg-gray-100"
//         >
//           Explore Activities
//         </Link>
//       </section>

//       {/* Dynamic Statistics */}
//       <section className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
//         {stats.map((stat) => {
//           const Icon = stat.icon;

//           return (
//             <div
//               key={stat.label}
//               className="rounded-xl border border-[#E1EAE4] bg-white p-5"
//             >
//               <div className="flex items-center justify-between">
//                 <p className="text-sm text-gray-500">
//                   {stat.label}
//                 </p>

//                 <Icon size={22} className="text-[#315C4A]" />
//               </div>

//               <p className="mt-3 text-3xl font-bold">
//                 {activitiesLoading ? "--" : stat.value}
//               </p>
//             </div>
//           );
//         })}
//       </section>

//       <div className="mt-7 grid grid-cols-1 gap-6 xl:grid-cols-3">
//         {/* Latest Activities */}
//         <section className="rounded-xl border border-[#E1EAE4] bg-white p-5 xl:col-span-2">
//           <div className="flex items-center justify-between gap-3">
//             <div>
//               <h3 className="font-bold">
//                 Latest Activities
//               </h3>

//               <p className="mt-1 text-sm text-gray-500">
//                 Discover the latest published activities and events.
//               </p>
//             </div>

//             <Link
//               to="/dashboard/activities"
//               className="shrink-0 text-sm font-semibold text-[#315C4A] hover:underline"
//             >
//               View all
//             </Link>
//           </div>

//           <div className="mt-5 space-y-3">
//             {/* Loading */}
//             {activitiesLoading && (
//               <div className="py-10 text-center">
//                 <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-[#315C4A] border-t-transparent" />

//                 <p className="mt-3 text-sm text-gray-500">
//                   Loading activities...
//                 </p>
//               </div>
//             )}

//             {/* Error */}
//             {!activitiesLoading && activitiesError && (
//               <div className="rounded-lg bg-red-50 p-5 text-center">
//                 <p className="text-sm text-red-600">
//                   {activitiesError}
//                 </p>

//                 <button
//                   type="button"
//                   onClick={() => void fetchActivities()}
//                   className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
//                 >
//                   <RefreshCw size={15} />
//                   Try again
//                 </button>
//               </div>
//             )}

//             {/* Empty State */}
//             {!activitiesLoading &&
//               !activitiesError &&
//               latestActivities.length === 0 && (
//                 <div className="rounded-lg border border-dashed border-gray-200 py-10 text-center">
//                   <CalendarDays
//                     size={32}
//                     className="mx-auto text-gray-400"
//                   />

//                   <h4 className="mt-3 font-semibold text-gray-700">
//                     No activities available
//                   </h4>

//                   <p className="mt-1 text-sm text-gray-500">
//                     New activities will appear here when published.
//                   </p>

//                   <Link
//                     to="/activities"
//                     className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//                   >
//                     Explore activities
//                   </Link>
//                 </div>
//               )}

//             {/* Activity List */}
//             {!activitiesLoading &&
//               !activitiesError &&
//               latestActivities.map((activity) => (
//                 <div
//                   key={activity.id}
//                   className="rounded-lg border border-gray-100 p-4 transition hover:border-[#B9D0C2] hover:bg-[#F8FBF9]"
//                 >
//                   <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
//                     <div className="min-w-0 flex-1">
//                       <div className="flex flex-wrap items-center gap-2">
//                         <h4 className="font-semibold text-gray-800">
//                           {activity.activity_name || activity.title}
//                         </h4>

//                         {activity.is_featured && (
//                           <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
//                             Featured
//                           </span>
//                         )}

//                         {activity.is_important && (
//                           <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-600">
//                             Important
//                           </span>
//                         )}
//                       </div>

//                       <p className="mt-2 line-clamp-2 text-sm leading-6 text-gray-500">
//                         {activity.short_description ||
//                           "View details to learn more about this activity."}
//                       </p>

//                       <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-gray-500">
//                         {activity.category?.name && (
//                           <span className="rounded-full bg-[#E8F1EC] px-3 py-1 font-medium text-[#315C4A]">
//                             {activity.category.name}
//                           </span>
//                         )}

//                         <span className="inline-flex items-center gap-1">
//                           <CalendarDays size={14} />
//                           {formatDate(
//                             activity.start_date || activity.event_date
//                           )}
//                         </span>

//                         {activity.location && (
//                           <span className="inline-flex items-center gap-1">
//                             <MapPin size={14} />
//                             {activity.location}
//                           </span>
//                         )}
//                       </div>
//                     </div>

//                     <Link
//                       to={`/activities/${activity.id}`}
//                       className="w-fit shrink-0 text-sm font-semibold text-[#315C4A] hover:underline"
//                     >
//                       View Details →
//                     </Link>
//                   </div>
//                 </div>
//               ))}
//           </div>
//         </section>

//         {/* Dynamic Profile Summary */}
//         <section className="rounded-xl border border-[#E1EAE4] bg-white p-5">
//           <div className="flex items-center justify-between">
//             <h3 className="font-bold">
//               My Profile
//             </h3>

//             <Link
//               to="/dashboard/profile/edit"
//               className="text-sm font-semibold text-[#315C4A] hover:underline"
//             >
//               Edit
//             </Link>
//           </div>

//           {profileLoading ? (
//             <div className="mt-8 py-8 text-center text-sm text-gray-500">
//               Loading your profile...
//             </div>
//           ) : profileError ? (
//             <div className="mt-8 text-center">
//               <p className="text-sm text-red-500">
//                 {profileError}
//               </p>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//               >
//                 Open Profile
//               </Link>
//             </div>
//           ) : profile ? (
//             <>
//               {/* Profile Picture and Name */}
//               <div className="mt-5 flex flex-col items-center text-center">
//                 {profile.profile_picture_url ? (
//                   <img
//                     src={profile.profile_picture_url}
//                     alt={fullName}
//                     className="h-20 w-20 rounded-full border-2 border-[#E1EAE4] object-cover"
//                   />
//                 ) : (
//                   <div className="grid h-20 w-20 place-items-center rounded-full bg-[#E8F1EC] text-2xl font-bold text-[#315C4A]">
//                     {initials || "U"}
//                   </div>
//                 )}

//                 <h4 className="mt-3 font-bold">
//                   {fullName}
//                 </h4>

//                 <p className="text-sm text-gray-500">
//                   {roleLabel}
//                 </p>

//                 <p className="mt-1 text-xs text-gray-400">
//                   @{profile.username}
//                 </p>
//               </div>

//               {/* Profile Information */}
//               <div className="mt-5 space-y-4 border-t border-gray-100 pt-4 text-sm">
//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Email
//                   </p>

//                   <p className="mt-1 break-all font-medium">
//                     {profile.email || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Phone Number
//                   </p>

//                   <p className="mt-1 font-medium">
//                     {profile.phone_number || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Country
//                   </p>

//                   <p className="mt-1 font-medium">
//                     {profile.country || "Not provided"}
//                   </p>
//                 </div>

//                 <div>
//                   <p className="text-xs text-gray-400">
//                     Bio
//                   </p>

//                   <p className="mt-1 break-words text-gray-600">
//                     {profile.bio ||
//                       "Add a short introduction about yourself."}
//                   </p>
//                 </div>
//               </div>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-5 block rounded-lg border border-[#315C4A] py-2.5 text-center text-sm font-semibold text-[#315C4A] hover:bg-[#E8F1EC]"
//               >
//                 View Full Profile
//               </Link>
//             </>
//           ) : (
//             <div className="mt-6 text-center">
//               <p className="text-sm text-gray-500">
//                 Profile information is not available.
//               </p>

//               <Link
//                 to="/dashboard/profile"
//                 className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//               >
//                 Open Profile
//               </Link>
//             </div>
//           )}
//         </section>
//       </div>

//       {/* Skills and Interests */}
//       <section className="mt-6 rounded-xl border border-[#E1EAE4] bg-white p-5">
//         <h3 className="font-bold">
//           My Skills & Interests
//         </h3>

//         <p className="mt-1 text-sm text-gray-500">
//           Add your interests and skills to improve your profile.
//         </p>

//         {/* <p className="mt-4 text-sm text-gray-500">
//           Visit your profile to manage your personal information.
//         </p>

//         <Link
//           to="/dashboard/profile"
//           className="mt-3 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
//         >
//           Manage Profile →
//         </Link> */}
//       </section>
//     </DashboardLayout>
//   );
// }






import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
  Pencil,
  Lightbulb,
  Code,
  RefreshCw,
  UserRound,
  Award,
  CheckCircle,
  ArrowRight,
  Mail,
  MapPin,
  Phone,
  BookOpen,
  Sparkles,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import profileService from "../../services/profileService";
import type { UserProfile } from "../../types/profile";

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

export default function UserDashboard() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState("");

  // Fetch logged-in user's profile
  const fetchProfile = async () => {
    try {
      setProfileLoading(true);
      setProfileError("");

      const data = await profileService.getMyProfile();
      setProfile(data);
    } catch (error) {
      console.error("Failed to load profile:", error);
      setProfileError("Unable to load your profile. Please try again.");
    } finally {
      setProfileLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    const loadProfile = async () => {
      try {
        const data = await profileService.getMyProfile();

        if (active) {
          setProfile(data);
          setProfileError("");
        }
      } catch (error) {
        console.error("Failed to load profile:", error);

        if (active) {
          setProfileError("Unable to load your profile. Please try again.");
        }
      } finally {
        if (active) {
          setProfileLoading(false);
        }
      }
    };

    void loadProfile();

    return () => {
      active = false;
    };
  }, []);

  const fullName =
    profile?.full_name || profile?.username || "Student";

  const roleLabel =
    profile?.role === "user"
      ? "Student"
      : profile?.role === "coordinator"
        ? "Coordinator"
        : profile?.role === "admin"
          ? "Administrator"
          : "User";

  const initials = fullName
    .split(" ")
    .filter(Boolean)
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const skills = profile?.skills ?? [];
  const interests = profile?.interests ?? [];

  // Calculate profile completion from actual profile information
  const profileFields = profile
    ? [
        profile.full_name,
        profile.username,
        profile.email,
        profile.phone_number,
        profile.country,
        profile.date_of_birth,
        profile.bio,
        profile.profile_picture_url,
        skills.length > 0,
        interests.length > 0,
      ]
    : [];

  const completedFields = profileFields.filter(Boolean).length;

  const profileCompletion =
    profileFields.length > 0
      ? Math.round((completedFields / profileFields.length) * 100)
      : 0;

  return (
    <DashboardLayout
      role="user"
      title="My Dashboard"
      subtitle="Your personal overview of skills, interests and profile progress."
      navItems={navItems}
    >
      <div className="space-y-7">

        {/* Welcome Section */}
        <section className="relative overflow-hidden rounded-2xl bg-[#315C4A] p-6 text-white sm:p-8">
          <div className="relative z-10 max-w-2xl">
            <p className="text-sm font-medium text-white/75">
              Welcome back,
            </p>

            <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
              {profileLoading ? "Loading..." : fullName}
            </h2>

            <p className="mt-3 text-sm leading-6 text-white/80">
              Continue building your extra-curricular portfolio.
              Explore opportunities, develop your skills, and showcase
              your achievements.
            </p>

            <Link
              to="/dashboard/activities"
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-[#315C4A] transition hover:bg-gray-100"
            >
              Explore Activities
              <ArrowRight size={16} />
            </Link>
          </div>

          <div className="pointer-events-none absolute -right-10 -top-16 h-64 w-64 rounded-full border-[35px] border-white/10" />
          <div className="pointer-events-none absolute -bottom-28 right-24 h-64 w-64 rounded-full border-[35px] border-white/10" />
        </section>

        {/* Loading and Error States */}
        {profileError && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-600">{profileError}</p>

            <button
              type="button"
              onClick={() => void fetchProfile()}
              className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
            >
              <RefreshCw size={15} />
              Try again
            </button>
          </div>
        )}

        {/* Overview Statistics */}
        <section>
          <div className="mb-4">
            <h3 className="text-lg font-bold text-gray-800">
              Your Overview
            </h3>

            <p className="mt-1 text-sm text-gray-500">
              A quick look at your profile and development.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {/* Skills */}
            <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="rounded-lg bg-[#E8F1EC] p-3">
                  <Code size={21} className="text-[#315C4A]" />
                </div>

                <span className="text-xs text-gray-400">
                  My Skills
                </span>
              </div>

              <h3 className="mt-4 text-3xl font-bold text-gray-800">
                {profileLoading ? "--" : skills.length}
              </h3>

              <p className="mt-1 text-sm text-gray-500">
                Skills added
              </p>
            </div>

            {/* Interests */}
            <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="rounded-lg bg-[#F0ECF8] p-3">
                  <Lightbulb size={21} className="text-purple-600" />
                </div>

                <span className="text-xs text-gray-400">
                  My Interests
                </span>
              </div>

              <h3 className="mt-4 text-3xl font-bold text-gray-800">
                {profileLoading ? "--" : interests.length}
              </h3>

              <p className="mt-1 text-sm text-gray-500">
                Interests added
              </p>
            </div>

            {/* Profile Completion */}
            <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="rounded-lg bg-[#FFF4E5] p-3">
                  <UserRound size={21} className="text-orange-500" />
                </div>

                <span className="text-xs text-gray-400">
                  Profile
                </span>
              </div>

              <h3 className="mt-4 text-3xl font-bold text-gray-800">
                {profileLoading ? "--" : `${profileCompletion}%`}
              </h3>

              <p className="mt-1 text-sm text-gray-500">
                Profile completed
              </p>
            </div>

            {/* Email Verification */}
            <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="rounded-lg bg-[#E8F3F0] p-3">
                  <Mail size={21} className="text-teal-600" />
                </div>

                <span className="text-xs text-gray-400">
                  Account
                </span>
              </div>

              <h3 className="mt-4 text-xl font-bold text-gray-800">
                {profileLoading
                  ? "Loading"
                  : profile?.is_email_verified
                    ? "Verified"
                    : "Pending"}
              </h3>

              <p className="mt-1 text-sm text-gray-500">
                Email verification
              </p>
            </div>
          </div>
        </section>

        {/* Profile Completion */}
        {!profileLoading && !profileError && profile && profileCompletion < 100 && (
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <div className="flex items-center gap-2">
                  <Sparkles size={19} className="text-[#315C4A]" />

                  <h3 className="font-bold text-gray-800">
                    Complete Your Profile
                  </h3>
                </div>

                <p className="mt-2 text-sm text-gray-500">
                  Add your missing information to build a stronger
                  student portfolio.
                </p>
              </div>

              <Link
                to="/dashboard/profile/edit"
                className="inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
              >
                Complete Profile
                <ArrowRight size={16} />
              </Link>
            </div>

            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">
                  Profile completion
                </span>

                <span className="text-sm font-bold text-[#315C4A]">
                  {profileCompletion}%
                </span>
              </div>

              <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-[#315C4A] transition-all duration-500"
                  style={{ width: `${profileCompletion}%` }}
                />
              </div>
            </div>
          </section>
        )}

        {/* Main Dashboard Content */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">

          {/* Skills and Interests */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-5 xl:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-gray-800">
                  My Skills & Interests
                </h3>

                <p className="mt-1 text-sm text-gray-500">
                  Showcase your strengths and areas of interest.
                </p>
              </div>

              <Link
                to="/dashboard/profile/edit"
                className="inline-flex shrink-0 items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
              >
                <Pencil size={15} />
                Edit
              </Link>
            </div>

            {profileLoading ? (
              <div className="py-12 text-center">
                <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-[#315C4A] border-t-transparent" />

                <p className="mt-3 text-sm text-gray-500">
                  Loading your skills and interests...
                </p>
              </div>
            ) : profileError ? (
              <div className="py-10 text-center text-sm text-gray-500">
                Profile information could not be loaded.
              </div>
            ) : (
              <div className="mt-6 space-y-7">

                {/* Skills */}
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <div className="rounded-lg bg-[#E8F1EC] p-2">
                      <Code size={19} className="text-[#315C4A]" />
                    </div>

                    <div>
                      <h4 className="font-semibold text-gray-800">
                        Skills
                      </h4>

                      <p className="text-xs text-gray-500">
                        {skills.length} {skills.length === 1 ? "skill" : "skills"} added
                      </p>
                    </div>
                  </div>

                  {skills.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {skills.map((skill, index) => (
                        <span
                          key={`${skill}-${index}`}
                          className="rounded-full border border-[#D5E5DA] bg-[#F3F8F5] px-4 py-2 text-sm font-medium text-[#315C4A]"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-gray-200 px-4 py-6 text-center">
                      <p className="text-sm text-gray-500">
                        You haven't added any skills yet.
                      </p>

                      <Link
                        to="/dashboard/profile/edit"
                        className="mt-2 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
                      >
                        Add your skills
                      </Link>
                    </div>
                  )}
                </div>

                {/* Interests */}
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <div className="rounded-lg bg-[#E8F1EC] p-2">
                      <Lightbulb size={19} className="text-[#315C4A]" />
                    </div>

                    <div>
                      <h4 className="font-semibold text-gray-800">
                        Interests
                      </h4>

                      <p className="text-xs text-gray-500">
                        {interests.length}{" "}
                        {interests.length === 1 ? "interest" : "interests"} added
                      </p>
                    </div>
                  </div>

                  {interests.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {interests.map((interest, index) => (
                        <span
                          key={`${interest}-${index}`}
                          className="rounded-full border border-[#DCE5F2] bg-[#F3F7FC] px-4 py-2 text-sm font-medium text-[#315C4A]"
                        >
                          {interest}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-gray-200 px-4 py-6 text-center">
                      <p className="text-sm text-gray-500">
                        You haven't added any interests yet.
                      </p>

                      <Link
                        to="/dashboard/profile/edit"
                        className="mt-2 inline-block text-sm font-semibold text-[#315C4A] hover:underline"
                      >
                        Add your interests
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            )}

            {!profileLoading && !profileError && (
              <Link
                to="/dashboard/profile"
                className="mt-7 block rounded-lg border border-[#315C4A] py-2.5 text-center text-sm font-semibold text-[#315C4A] transition hover:bg-[#E8F1EC]"
              >
                View Full Profile
              </Link>
            )}
          </section>

          {/* Profile Summary */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-gray-800">
                My Profile
              </h3>

              <Link
                to="/dashboard/profile/edit"
                className="text-sm font-semibold text-[#315C4A] hover:underline"
              >
                Edit
              </Link>
            </div>

            {profileLoading ? (
              <div className="mt-8 py-8 text-center text-sm text-gray-500">
                Loading your profile...
              </div>
            ) : profileError ? (
              <div className="mt-8 text-center text-sm text-red-500">
                Unable to load profile information.
              </div>
            ) : profile ? (
              <>
                {/* Profile Picture */}
                <div className="mt-5 flex flex-col items-center text-center">
                  {profile.profile_picture_url ? (
                    <img
                      src={profile.profile_picture_url}
                      alt={fullName}
                      className="h-20 w-20 rounded-full border-2 border-[#E1EAE4] object-cover"
                    />
                  ) : (
                    <div className="grid h-20 w-20 place-items-center rounded-full bg-[#E8F1EC] text-2xl font-bold text-[#315C4A]">
                      {initials || "U"}
                    </div>
                  )}

                  <h4 className="mt-3 font-bold text-gray-800">
                    {fullName}
                  </h4>

                  <p className="text-sm text-gray-500">
                    {roleLabel}
                  </p>

                  <p className="mt-1 text-xs text-gray-400">
                    @{profile.username}
                  </p>
                </div>

                {/* Profile Details */}
                <div className="mt-5 space-y-4 border-t border-gray-100 pt-4 text-sm">

                  <div className="flex items-start gap-3">
                    <Mail size={16} className="mt-0.5 shrink-0 text-[#315C4A]" />

                    <div className="min-w-0">
                      <p className="text-xs text-gray-400">
                        Email
                      </p>

                      <p className="mt-1 break-all font-medium text-gray-700">
                        {profile.email || "Not provided"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <Phone size={16} className="mt-0.5 shrink-0 text-[#315C4A]" />

                    <div>
                      <p className="text-xs text-gray-400">
                        Phone Number
                      </p>

                      <p className="mt-1 font-medium text-gray-700">
                        {profile.phone_number || "Not provided"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <MapPin size={16} className="mt-0.5 shrink-0 text-[#315C4A]" />

                    <div>
                      <p className="text-xs text-gray-400">
                        Country
                      </p>

                      <p className="mt-1 font-medium text-gray-700">
                        {profile.country || "Not provided"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <BookOpen size={16} className="mt-0.5 shrink-0 text-[#315C4A]" />

                    <div>
                      <p className="text-xs text-gray-400">
                        About Me
                      </p>

                      <p className="mt-1 break-words text-gray-600">
                        {profile.bio || "Add a short introduction about yourself."}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t border-gray-100 pt-4">
                    <span className="text-xs text-gray-500">
                      Email Verification
                    </span>

                    {profile.is_email_verified ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-600">
                        <CheckCircle size={14} />
                        Verified
                      </span>
                    ) : (
                      <span className="text-xs font-semibold text-orange-500">
                        Not verified
                      </span>
                    )}
                  </div>
                </div>

                <Link
                  to="/dashboard/profile"
                  className="mt-5 block rounded-lg border border-[#315C4A] py-2.5 text-center text-sm font-semibold text-[#315C4A] transition hover:bg-[#E8F1EC]"
                >
                  View Full Profile
                </Link>
              </>
            ) : (
              <div className="mt-6 text-center">
                <p className="text-sm text-gray-500">
                  Profile information is not available.
                </p>
              </div>
            )}
          </section>
        </div>

        {/* Quick Actions */}
        <section>
          <div className="mb-4">
            <h3 className="text-lg font-bold text-gray-800">
              Quick Actions
            </h3>

            <p className="mt-1 text-sm text-gray-500">
              Quickly access the main features of your dashboard.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">

            <Link
              to="/dashboard/activities"
              className="group flex items-center justify-between rounded-xl border border-[#E1EAE4] bg-white p-5 transition hover:-translate-y-1 hover:border-[#315C4A] hover:shadow-md"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-[#E8F1EC] p-3">
                  <ClipboardList size={22} className="text-[#315C4A]" />
                </div>

                <div>
                  <h4 className="font-semibold text-gray-800">
                    Explore Activities
                  </h4>

                  <p className="mt-1 text-xs text-gray-500">
                    Discover opportunities
                  </p>
                </div>
              </div>

              <ArrowRight
                size={18}
                className="text-gray-400 transition group-hover:translate-x-1 group-hover:text-[#315C4A]"
              />
            </Link>

            <Link
              to="/dashboard/achievements"
              className="group flex items-center justify-between rounded-xl border border-[#E1EAE4] bg-white p-5 transition hover:-translate-y-1 hover:border-[#315C4A] hover:shadow-md"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-[#FFF4E5] p-3">
                  <Award size={22} className="text-orange-500" />
                </div>

                <div>
                  <h4 className="font-semibold text-gray-800">
                    My Certificates
                  </h4>

                  <p className="mt-1 text-xs text-gray-500">
                    View your recognition
                  </p>
                </div>
              </div>

              <ArrowRight
                size={18}
                className="text-gray-400 transition group-hover:translate-x-1 group-hover:text-[#315C4A]"
              />
            </Link>

            <Link
              to="/dashboard/profile"
              className="group flex items-center justify-between rounded-xl border border-[#E1EAE4] bg-white p-5 transition hover:-translate-y-1 hover:border-[#315C4A] hover:shadow-md"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-[#F0ECF8] p-3">
                  <CircleUserRound size={22} className="text-purple-600" />
                </div>

                <div>
                  <h4 className="font-semibold text-gray-800">
                    My Profile
                  </h4>

                  <p className="mt-1 text-xs text-gray-500">
                    Manage your information
                  </p>
                </div>
              </div>

              <ArrowRight
                size={18}
                className="text-gray-400 transition group-hover:translate-x-1 group-hover:text-[#315C4A]"
              />
            </Link>

          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
