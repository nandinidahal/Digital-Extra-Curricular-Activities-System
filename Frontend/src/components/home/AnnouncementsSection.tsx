import { useEffect, useState } from "react";
import SectionHeading from "../common/SectionHeading";
import { activityService } from "../../services/activityService";
import { mockAnnouncements } from "../../data/mockData";
import { formatDate } from "../../utils/format";
import type { Announcement } from "../../types";

export default function AnnouncementsSection() {
  const [items, setItems] = useState<Announcement[]>([]);

  useEffect(() => {
    activityService
      .announcements()
      .then((list) => setItems(list.slice(0, 3)))
      .catch(() => setItems(mockAnnouncements));
  }, []);

  return (
    <section id="news" className="container-page py-20">
      <SectionHeading title="Latest announcements" />

      <ul className="mt-10 divide-y divide-pine-100 border-y border-pine-100">
        {items.map((a) => (
          <li key={a.id} className="grid gap-1 py-5 md:grid-cols-4 md:gap-6">
            <time className="text-sm text-ink/60">{formatDate(a.published_at)}</time>
            <div className="md:col-span-3">
              <h3 className="text-lg font-bold">{a.title}</h3>
              <p className="mt-1 text-ink/70">{a.description}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
