

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

/* ---------- Static sample data (replace with API calls later) ---------- */

const student = { name: "Krishna", program: "BSc Computer Science, second year" };

const stats = [
  { label: "Activities joined", value: "12" },
  { label: "Certificates", value: "7" },
  { label: "Service credits", value: "9 of 12", progress: 75 },
  { label: "Upcoming events", value: "3" },
];

const upcoming = [
  { id: 1, title: "Inter-College Futsal Cup", date: "14 Nov", time: "9:00 AM", venue: "College Ground", status: "Registered" },
  { id: 2, title: "48-Hour Campus Hackathon", date: "21 Nov", time: "10:00 AM", venue: "Computer Lab 2", status: "Waitlisted" },
  { id: 3, title: "Cultural Night", date: "2 Dec", time: "4:00 PM", venue: "Main Auditorium", status: "Registered" },
];

const certificates = [
  { id: 1, title: "Photography Walk", issuer: "Arts & Visual Media Guild", date: "24 Oct 2026", verified: true },
  { id: 2, title: "Blood Donation Drive", issuer: "International Red Cross", date: "20 Oct 2026", verified: true },
  { id: 3, title: "Web3 & AI Sprint", issuer: "CS & Innovation Hub", date: "18 Oct 2026", verified: false },
];

const initialNotifications = [
  { id: 1, text: "Futsal Cup registrations close on 8 November.", time: "2 hours ago", read: false },
  { id: 2, text: "Your Photography Walk certificate is ready to download.", time: "Yesterday", read: false },
  { id: 3, text: "Mentor room allocations for the Sprint were announced.", time: "3 days ago", read: true },
];

const quickLinks = [
  { label: "Browse activities", to: "/activities" },
  { label: "My certificates", to: "/student/certificates" },
  { label: "My achievements", to: "/student/achievements" },
  { label: "Edit profile", to: "/student/profile" },
];

/* ---------- Bell + dropdown ---------- */

function BellIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState(initialNotifications);
  const ref = useRef<HTMLDivElement>(null);
  const unread = items.filter((n) => !n.read).length;

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
        className="relative grid h-10 w-10 place-items-center rounded-full border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
      >
        <BellIcon />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
            <p className="text-sm font-semibold text-gray-900">Notifications</p>
            {unread > 0 && (
              <button
                onClick={() => setItems((l) => l.map((n) => ({ ...n, read: true })))}
                className="text-xs text-pine-700 hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>
          <ul className="max-h-80 divide-y divide-gray-100 overflow-y-auto">
            {items.map((n) => (
              <li key={n.id} className={`flex gap-3 px-4 py-3 ${n.read ? "" : "bg-pine-50"}`}>
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-pine-600"}`} />
                <div>
                  <p className="text-sm text-gray-800">{n.text}</p>
                  <p className="mt-0.5 text-xs text-gray-500">{n.time}</p>
                </div>
              </li>
            ))}
          </ul>
          <Link
            to="/student/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-gray-100 px-4 py-2.5 text-center text-sm text-pine-700 hover:bg-gray-50"
          >
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

/* ---------- Page ---------- */

function Card({ title, link, children }: { title: string; link?: { label: string; to: string }; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        {link && (
          <Link to={link.to} className="text-sm text-pine-700 hover:underline">
            {link.label}
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

export default function Dashboard() {
  return (
    <main className="container-page max-w-6xl py-8 pb-16">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Hi, {student.name}</h1>
          <p className="mt-1 text-sm text-gray-600">{student.program}</p>
        </div>
        <NotificationBell />
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-sm text-gray-600">{s.label}</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{s.value}</p>
            {s.progress !== undefined && (
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div className="h-full rounded-full bg-pine-600" style={{ width: `${s.progress}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <Card title="Upcoming activities" link={{ label: "View all", to: "/student/activities" }}>
            <ul className="divide-y divide-gray-100">
              {upcoming.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                  <div className="flex items-center gap-4">
                    <div className="w-12 shrink-0 text-center">
                      <p className="text-lg font-semibold leading-none text-gray-900">{a.date.split(" ")[0]}</p>
                      <p className="mt-1 text-xs uppercase text-gray-500">{a.date.split(" ")[1]}</p>
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{a.title}</p>
                      <p className="text-sm text-gray-600">
                        {a.time} · {a.venue}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      a.status === "Registered" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {a.status}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Recent certificates" link={{ label: "View all", to: "/student/certificates" }}>
            <ul className="divide-y divide-gray-100">
              {certificates.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                  <div>
                    <p className="font-medium text-gray-900">{c.title}</p>
                    <p className="text-sm text-gray-600">
                      {c.issuer} · {c.date}
                    </p>
                  </div>
                  <span className={`shrink-0 text-xs font-medium ${c.verified ? "text-green-700" : "text-gray-500"}`}>
                    {c.verified ? "Verified" : "Pending"}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <Card title="Quick links">
          <ul className="divide-y divide-gray-100">
            {quickLinks.map((l) => (
              <li key={l.to}>
                <Link to={l.to} className="flex items-center justify-between px-5 py-3 text-sm text-gray-800 hover:bg-gray-50">
                  {l.label}
                  <span className="text-gray-400" aria-hidden>
                    ›
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </main>
  );
}
