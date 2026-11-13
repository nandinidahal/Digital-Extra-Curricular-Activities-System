import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { Activity } from "../../types";
import { formatDate } from "../../utils/format";
import StatusBadge from "./StatusBadge";
import { activityService } from "../../services/activityService";
import { mockActivities } from "../../data/mockData";



// /*
//  * Optional extra fields to add to your Activity type (hidden when missing):
//  *   description?: string;
//  *   highlights?: string[];      // "What to know" bullets
//  *   organizer?: string;
//  *   format?: string;
//  *   registration_deadline?: string;
//  *   reward?: string;
//  *   time?: string;
//  */

export default function ActivityDetail() {
  const { id } = useParams();
  const [activity, setActivity] = useState<Activity | null>(null);
  const [registered, setRegistered] = useState(false);

//   useEffect(() => {
//     // Replace `get` with whatever your service exposes for a single activity
//     activityService.get(Number(id)).then(setActivity).catch(() => setActivity(null));
//   }, [id]);
useEffect(() => {
  if (!id) return;
  activityService
    .get(id)
    .then((data) => {
      console.log("activity response:", data); // temporary, shows what the API sends
      if (!data || typeof data !== "object" || !("title" in data)) {
        throw new Error("Unexpected response");
      }
      setActivity(data);
    })
    .catch(() => setActivity(mockActivities.find((a) => a.id === Number(id)) ?? null));
}, [id]);

  if (!activity) return <p className="container-page py-20 text-ink/60">Loading…</p>;

  const slotsLeft = activity.max_participants - activity.registered_count;
  const filled = Math.min(100, (activity.registered_count / activity.max_participants) * 100);

  const facts = [
    ["Organised by", activity.organizer],
    ["Format", activity.format],
    // ["Registration closes", activity.registration_deadline && formatDate(activity.registration_deadline)],
    ["Registration closes", activity.deadline && formatDate(activity.deadline)],
    ["Reward", activity.reward],
  ].filter(([, v]) => v) as [string, string][];

  return (
    <main className="container-page max-w-4xl py-8 pb-16">
      <Link to="/activities" className="text-xs text-ink/60 hover:underline">
        ← Back to activities
      </Link>

      {activity.banner ? (
        <img src={activity.banner} alt="" className="mt-4 h-56 w-full rounded-[18px] object-cover" />
      ) : (
        <div className="mt-4 grid h-56 place-items-center rounded-[18px] bg-gradient-to-br from-[#163b2b] to-[#2e6b4f] font-serif text-8xl font-semibold text-white/30">
          {/* {activity.category_name[0]} */}
          {/* {(activity.category_name ?? activity.title)[0]} */}
          {(activity.category_name ?? activity.title ?? "?")[0]}
        </div>
      )}

      <div className="mt-7 grid items-start gap-9 md:grid-cols-[1fr_290px]">
        {/* Main content */}
        <div>
          <div className="flex items-center gap-2.5 text-xs">
            <span className="font-semibold text-pine-700">{activity.category_name}</span>
            <StatusBadge status={activity.status} />
          </div>

          <h1 className="mt-2.5 font-serif text-[32px] font-semibold leading-tight">{activity.title}</h1>
          {activity.description && (
            <p className="mt-3.5 max-w-[520px] text-ink/65">{activity.description}</p>
          )}

          {activity.highlights?.length ? (
            <>
              <h2 className="mt-8 border-t border-[#e6e4dc] pt-5 font-serif text-lg font-semibold">What to know</h2>
              <ul className="mt-2.5 list-disc space-y-1.5 pl-5 text-ink/65">
                {activity.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            </>
          ) : null}

          {facts.length > 0 && (
            <>
              <h2 className="mt-8 border-t border-[#e6e4dc] pt-5 font-serif text-lg font-semibold">Details</h2>
              <dl className="mt-3 grid grid-cols-2 gap-3">
                {facts.map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-[#e6e4dc] bg-[#f0efe8] px-3.5 py-3">
                    <dt className="text-[11px] text-ink/55">{label}</dt>
                    <dd className="font-semibold">{value}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </div>

        {/* Registration card */}
        <aside className="rounded-[18px] border border-[#e6e4dc] bg-white p-5 md:sticky md:top-5">
          <Row label="Date" value={formatDate(activity.date)} />
          {/* {activity.time && <Row label="Time" value={activity.time} />} */}
          {activity.start_time && <Row label="Time" value={activity.start_time} />}
          <Row label="Venue" value={activity.venue} />

          <div className="mt-4 h-[7px] overflow-hidden rounded-full bg-[#f0efe8]">
            <div className="h-full bg-[#e8a63a]" style={{ width: `${filled}%` }} />
          </div>
          <p className="mt-2 text-xs text-ink/55">
            {slotsLeft > 0 ? `${slotsLeft} slots left of ${activity.max_participants}` : "No slots left"}
          </p>

          <button
            disabled={registered || slotsLeft <= 0}
            onClick={() => {
              // TODO: call your registration endpoint, then:
              setRegistered(true);
            }}
            className="mt-4 w-full rounded-[10px] bg-[#163b2b] py-3 text-sm font-semibold text-white hover:brightness-110 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 focus-visible:outline-[#e8a63a] disabled:bg-[#d3f0e0] disabled:text-[#1d6b46]"
          >
            {registered ? "Registered ✓" : slotsLeft > 0 ? "Register now" : "Full"}
          </button>
        </aside>
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-[#e6e4dc] py-2.5 text-[13px]">
      <span className="text-ink/55">{label}</span>
      <b className="font-semibold">{value}</b>
    </div>
  );
}