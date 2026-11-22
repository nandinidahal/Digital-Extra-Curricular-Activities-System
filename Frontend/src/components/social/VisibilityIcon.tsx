import { Globe2, Lock, UserCheck, Users } from "lucide-react";
import type { PostVisibility } from "@/types/api";
import { visibilityLabels } from "@/utils/labels";

export function VisibilityIcon({ visibility, className = "h-3.5 w-3.5" }: { visibility: PostVisibility; className?: string }) {
  const Icon = visibility === "public" ? Globe2 : visibility === "members_only" ? Users : visibility === "friends" ? UserCheck : Lock;
  return (
    <span title={visibilityLabels[visibility]} className="inline-flex">
      <Icon className={className} aria-label={visibilityLabels[visibility]} />
    </span>
  );
}
