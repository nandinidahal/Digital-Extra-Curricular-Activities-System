
// import { useCallback, useEffect, useState } from "react";
// import { Link } from "react-router-dom";
// import { Plus, RefreshCw, Trophy } from "lucide-react";

// import DashboardLayout from "../../components/dashboard/DashboardLayout";
// import AchievementCard from "../../components/achievements/AchievementCard";
// import achievementService from "../../services/achievementService";
// import type { Achievement } from "../../types/achievement";

// import {
//   LayoutDashboard,
//   ClipboardList,
//   GraduationCap,
//   CircleUserRound,
// } from "lucide-react";

// const navItems = [
//   { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
//   {
//     label: "My Activities",
//     path: "/dashboard/activities",
//     icon: ClipboardList,
//   },
//   {
//     label: "Certificates",
//     path: "/dashboard/certificates",
//     icon: GraduationCap,
//   },
//   {
//     label: "My Profile",
//     path: "/dashboard/profile",
//     icon: CircleUserRound,
//   },
// ];

// export default function MyAchievementsPage() {
//   const [achievements, setAchievements] = useState<Achievement[]>([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState("");

//   const loadAchievements = useCallback(async () => {
//     try {
//       setLoading(true);
//       setError("");

//       const data = await achievementService.getMyAchievements();
//       setAchievements(data);
//     } catch (err) {
//       console.error("Failed to load achievements:", err);
//       setError("Unable to load your achievements. Please try again.");
//     } finally {
//       setLoading(false);
//     }
//   }, []);

//   useEffect(() => {
//     let active = true;

//     const fetchAchievements = async () => {
//       try {
//         const data = await achievementService.getMyAchievements();

//         if (active) {
//           setAchievements(data);
//           setError("");
//         }
//       } catch (err) {
//         console.error("Failed to load achievements:", err);

//         if (active) {
//           setError("Unable to load your achievements. Please try again.");
//         }
//       } finally {
//         if (active) {
//           setLoading(false);
//         }
//       }
//     };

//     void fetchAchievements();

//     return () => {
//       active = false;
//     };
//   }, []);

//   return (
//     <DashboardLayout
//       role="user"
//       title="My Achievements"
//       subtitle="Manage and showcase your accomplishments."
//       navItems={navItems}
//     >
//       <div className="flex flex-wrap items-center justify-between gap-4">
//         <div>
//           <h2 className="text-xl font-bold text-gray-900">
//             Achievement Portfolio
//           </h2>
//           <p className="mt-1 text-sm text-gray-500">
//             Your certificates, awards and accomplishments.
//           </p>
//         </div>

//         <Link
//           to="/dashboard/achievements/add"
//           className="inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-4 py-3 text-sm font-semibold text-white hover:bg-[#254938]"
//         >
//           <Plus size={18} />
//           Add Achievement
//         </Link>
//       </div>

//       <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
//         <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
//           <p className="text-sm text-gray-500">Total Achievements</p>
//           <p className="mt-2 text-3xl font-bold">
//             {achievements.length}
//           </p>
//         </div>

//         <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
//           <p className="text-sm text-gray-500">Public Achievements</p>
//           <p className="mt-2 text-3xl font-bold">
//             {
//               achievements.filter(
//                 (item) => item.visibility === "public"
//               ).length
//             }
//           </p>
//         </div>

//         <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
//           <p className="text-sm text-gray-500">Private Achievements</p>
//           <p className="mt-2 text-3xl font-bold">
//             {
//               achievements.filter(
//                 (item) => item.visibility === "private"
//               ).length
//             }
//           </p>
//         </div>
//       </div>

//       <div className="mt-7">
//         {loading ? (
//           <div className="py-16 text-center text-sm text-gray-500">
//             Loading your achievements...
//           </div>
//         ) : error ? (
//           <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-600">
//             <p>{error}</p>

//             <button
//               type="button"
//               onClick={loadAchievements}
//               className="mt-3 inline-flex items-center gap-2 font-semibold"
//             >
//               <RefreshCw size={15} />
//               Try again
//             </button>
//           </div>
//         ) : achievements.length === 0 ? (
//           <div className="rounded-xl border border-dashed border-gray-300 bg-white px-5 py-16 text-center">
//             <Trophy size={38} className="mx-auto text-[#315C4A]" />

//             <h3 className="mt-4 text-lg font-bold">
//               No achievements yet
//             </h3>

//             <p className="mt-2 text-sm text-gray-500">
//               Add your certificates, awards and other accomplishments here.
//             </p>

//             <Link
//               to="/dashboard/achievements/add"
//               className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-3 text-sm font-semibold text-white"
//             >
//               <Plus size={17} />
//               Add Your First Achievement
//             </Link>
//           </div>
//         ) : (
//           <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
//             {achievements.map((achievement) => (
//               <AchievementCard
//                 key={achievement.id}
//                 achievement={achievement}
//               />
//             ))}
//           </div>
//         )}
//       </div>
//     </DashboardLayout>
//   );
// }



import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, RefreshCw, Trophy } from "lucide-react";

import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import AchievementCard from "../../components/achievements/AchievementCard";
import achievementService from "../../services/achievementService";
import type { Achievement } from "../../types/achievement";

const navItems = [
  {
    label: "Overview",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "My Activities",
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

export default function MyAchievementsPage() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAchievements = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const data = await achievementService.getMyAchievements();

      setAchievements(data);
    } catch (err) {
      console.error("Failed to load achievements:", err);

      setError("Unable to load your achievements. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    const fetchAchievements = async () => {
      try {
        const data = await achievementService.getMyAchievements();

        if (active) {
          setAchievements(data);
          setError("");
        }
      } catch (err) {
        console.error("Failed to load achievements:", err);

        if (active) {
          setError("Unable to load your achievements. Please try again.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void fetchAchievements();

    return () => {
      active = false;
    };
  }, []);

  return (
    <DashboardLayout
      role="user"
      title="My Achievements"
      subtitle="Manage and showcase your accomplishments."
      navItems={navItems}
    >
      {/* Page Heading */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">
            Achievement Portfolio
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            Your certificates, awards and accomplishments.
          </p>
        </div>

        <Link
          to="/dashboard/achievements/add"
          className="inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-4 py-3 text-sm font-semibold text-white hover:bg-[#254938]"
        >
          <Plus size={18} />
          Add Achievement
        </Link>
      </div>

      {/* Achievement Statistics */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
          <p className="text-sm text-gray-500">
            Total Achievements
          </p>

          <p className="mt-2 text-3xl font-bold">
            {achievements.length}
          </p>
        </div>

        <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
          <p className="text-sm text-gray-500">
            Public Achievements
          </p>

          <p className="mt-2 text-3xl font-bold">
            {
              achievements.filter(
                (item) => item.visibility === "public"
              ).length
            }
          </p>
        </div>

        <div className="rounded-xl border border-[#E1EAE4] bg-white p-5">
          <p className="text-sm text-gray-500">
            Private Achievements
          </p>

          <p className="mt-2 text-3xl font-bold">
            {
              achievements.filter(
                (item) => item.visibility === "private"
              ).length
            }
          </p>
        </div>
      </div>

      {/* Achievement List */}
      <div className="mt-7">
        {loading ? (
          <div className="py-16 text-center text-sm text-gray-500">
            Loading your achievements...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-600">
            <p>{error}</p>

            <button
              type="button"
              onClick={loadAchievements}
              className="mt-3 inline-flex items-center gap-2 font-semibold"
            >
              <RefreshCw size={15} />
              Try again
            </button>
          </div>
        ) : achievements.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white px-5 py-16 text-center">
            <Trophy
              size={38}
              className="mx-auto text-[#315C4A]"
            />

            <h3 className="mt-4 text-lg font-bold">
              No achievements yet
            </h3>

            <p className="mt-2 text-sm text-gray-500">
              Add your certificates, awards and other accomplishments here.
            </p>

            <Link
              to="/dashboard/achievements/add"
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-3 text-sm font-semibold text-white"
            >
              <Plus size={17} />
              Add Your First Achievement
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {achievements.map((achievement) => (
              <AchievementCard
                key={achievement.id}
                achievement={achievement}
              />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
