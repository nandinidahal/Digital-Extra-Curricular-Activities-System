import type { ActivityStatus } from "../../types";
import { statusLabel } from "../../utils/format";

const colors: Record<ActivityStatus, string> = {
  draft: "bg-gray-200 text-gray-700",
  published: "bg-pine-50 text-pine-700",
  registration_open: "bg-green-100 text-green-800",
  registration_closed: "bg-orange-100 text-orange-800",
  ongoing: "bg-blue-100 text-blue-800",
  completed: "bg-gray-200 text-gray-700",
  cancelled: "bg-red-100 text-brick",
};

export default function StatusBadge({ status }: { status: ActivityStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${colors[status]}`}>
      {statusLabel[status]}
    </span>
  );
}
