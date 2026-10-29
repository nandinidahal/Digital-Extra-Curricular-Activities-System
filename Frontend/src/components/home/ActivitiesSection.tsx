import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ActivityCard from "../common/ActivityCard";
import SectionHeading from "../common/SectionHeading";
import { activityService } from "../../services/activityService";
import { mockActivities } from "../../data/mockData";
import type { Activity } from "../../types";

export default function ActivitiesSection() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    activityService
      .list({ status: "registration_open" })
      .then((data) => setActivities(data.results.slice(0, 3)))
      .catch(() => setActivities(mockActivities)) // backend not ready yet: show sample data
      .finally(() => setLoading(false));
  }, []);

  return (
    <section id="activities" className="container-page py-20">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeading title="Coming up on campus" text="Registration is open for these. Slots fill up fast." />
        <Link to="/activities" className="btn-outline">See all activities</Link>
      </div>

      {loading && <p className="mt-10 text-ink/70">Loading activities…</p>}
      {!loading && activities.length === 0 && (
        <p className="mt-10 rounded-xl bg-pine-50 p-6 text-ink/70">
          Nothing is open for registration right now. Check back soon.
        </p>
      )}

      <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {activities.map((a) => <ActivityCard key={a.id} activity={a} />)}
      </div>
    </section>
  );
}
