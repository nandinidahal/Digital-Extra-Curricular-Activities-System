
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import AchievementForm from "../../components/achievements/AchievementForm";
import achievementService from "../../services/achievementService";
import type {
  Achievement,
  AchievementFormData,
} from "../../types/achievement";

import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

const navItems = [
  { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { label: "My Activities", path: "/dashboard/activities", icon: ClipboardList },
  { label: "Certificates", path: "/dashboard/certificates", icon: GraduationCap },
  { label: "My Profile", path: "/dashboard/profile", icon: CircleUserRound },
];

export default function EditAchievementPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [achievement, setAchievement] = useState<Achievement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadAchievement = async () => {
      try {
        if (!id || !Number.isInteger(Number(id)) || Number(id) <= 0) {
          setError("Invalid achievement ID.");
          return;
        }

        const data = await achievementService.getMyAchievement(Number(id));
        setAchievement(data);
      } catch (err) {
        console.error("Failed to load achievement:", err);
        setError("Unable to load this achievement.");
      } finally {
        setLoading(false);
      }
    };

    loadAchievement();
  }, [id]);

  const handleSubmit = async (data: AchievementFormData) => {
    if (!id) return;

    await achievementService.updateAchievement(Number(id), data);
    navigate(`/dashboard/achievements/${id}`);
  };

  return (
    <DashboardLayout
      role="user"
      title="Edit Achievement"
      subtitle="Update your achievement information."
      navItems={navItems}
    >
      <button
        onClick={() => navigate(-1)}
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
      >
        <ArrowLeft size={17} />
        Go Back
      </button>

      <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 sm:p-7">
        {loading ? (
          <p className="py-10 text-center text-sm text-gray-500">
            Loading achievement...
          </p>
        ) : error ? (
          <p className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </p>
        ) : achievement ? (
          <>
            <h2 className="text-xl font-bold">Edit Achievement Information</h2>

            <div className="mt-7">
              <AchievementForm
                key={achievement.id}
                initialData={achievement}
                onSubmit={handleSubmit}
                submitLabel="Update Achievement"
              />
            </div>
          </>
        ) : null}
      </div>
    </DashboardLayout>
  );
}
