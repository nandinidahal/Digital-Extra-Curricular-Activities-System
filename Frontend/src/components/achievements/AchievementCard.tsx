
import { Link } from "react-router-dom";
import { CalendarDays, MapPin, Building2, Eye } from "lucide-react";

import type { Achievement } from "../../types/achievement";
import AchievementStatus from "./AchievementStatus";

type Props = {
  achievement: Achievement;
};

export default function AchievementCard({ achievement }: Props) {
  const formattedDate = new Date(
    `${achievement.achievement_date}T00:00:00`
  ).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <article className="rounded-xl border border-[#E1EAE4] bg-white p-5 transition hover:shadow-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[#315C4A]">
            {achievement.category.name}
          </p>

          <h3 className="mt-2 text-lg font-bold text-gray-900">
            {achievement.title}
          </h3>
        </div>

        <AchievementStatus
          visibility={achievement.visibility ?? "private"}
        />
      </div>

      <p className="mt-3 line-clamp-3 text-sm leading-6 text-gray-600">
        {achievement.description || "No description provided."}
      </p>

      <div className="mt-4 space-y-2 text-sm text-gray-500">
        <p className="flex items-center gap-2">
          <Building2 size={16} />
          {achievement.issuing_organization}
        </p>

        <p className="flex items-center gap-2">
          <CalendarDays size={16} />
          {formattedDate}
        </p>

        {achievement.location && (
          <p className="flex items-center gap-2">
            <MapPin size={16} />
            {achievement.location}
          </p>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-4">
        <span className="text-xs text-gray-500">
          {achievement.documents.length} document(s)
        </span>

        <Link
          to={`/dashboard/achievements/${achievement.id}`}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#315C4A] hover:underline"
        >
          <Eye size={16} />
          View Details
        </Link>
      </div>
    </article>
  );
}
