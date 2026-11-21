
import type { AchievementVisibility } from "../../types/achievement";

type Props = {
  visibility: AchievementVisibility;
};

export default function AchievementStatus({ visibility }: Props) {
  const isPublic = visibility === "public";

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        isPublic
          ? "bg-green-50 text-green-700"
          : "bg-gray-100 text-gray-600"
      }`}
    >
      {isPublic ? "Public" : "Private"}
    </span>
  );
}
