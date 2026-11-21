
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import AchievementForm from "../../components/achievements/AchievementForm";
import achievementService from "../../services/achievementService";
import type { AchievementFormData } from "../../types/achievement";

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

export default function AddAchievementPage() {
  const navigate = useNavigate();

  const handleSubmit = async (data: AchievementFormData) => {
    await achievementService.createAchievement(data);
    navigate("/dashboard/achievements");
  };

  return (
    <DashboardLayout
      role="user"
      title="Add Achievement"
      subtitle="Add a new accomplishment to your portfolio."
      navItems={navItems}
    >
      <button
        onClick={() => navigate("/dashboard/achievements")}
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
      >
        <ArrowLeft size={17} />
        Back to Achievements
      </button>

      <div className="rounded-xl border border-[#E1EAE4] bg-white p-5 sm:p-7">
        <h2 className="text-xl font-bold">Achievement Information</h2>
        <p className="mt-1 text-sm text-gray-500">
          Enter your achievement details and upload the related documents.
        </p>

        <div className="mt-7">
          <AchievementForm
            onSubmit={handleSubmit}
            submitLabel="Save Achievement"
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
