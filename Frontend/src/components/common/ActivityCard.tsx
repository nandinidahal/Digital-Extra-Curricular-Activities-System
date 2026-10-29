import { Link } from "react-router-dom";
import type { Activity } from "../../types";
import { formatDate } from "../../utils/format";
import StatusBadge from "./StatusBadge";

export default function ActivityCard({ activity }: { activity: Activity }) {
  const slotsLeft = activity.max_participants - activity.registered_count;

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-pine-100 bg-white">
      {/* Shows the uploaded banner, or a plain colour block if there is none */}
      {activity.banner ? (
        <img src={activity.banner} alt="" className="h-40 w-full object-cover" loading="lazy" />
      ) : (
        <div className="grid h-40 place-items-center bg-pine-50 font-display text-5xl font-bold text-pine-600/40">
          {activity.category_name[0]}
        </div>
      )}

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-pine-700">{activity.category_name}</span>
          <StatusBadge status={activity.status} />
        </div>

        <h3 className="mt-3 text-xl font-bold leading-snug">{activity.title}</h3>
        <p className="mt-2 text-sm text-ink/70">{formatDate(activity.date)} at {activity.venue}</p>
        <p className="mt-1 text-sm text-ink/70">{slotsLeft > 0 ? `${slotsLeft} slots left` : "No slots left"}</p>

        <Link to={`/activities/${activity.id}`} className="btn-outline mt-5 self-start">View details</Link>
      </div>
    </article>
  );
}
