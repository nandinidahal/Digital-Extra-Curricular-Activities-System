import { Bookmark, BookmarkCheck, CalendarDays, Globe2, Lock, MapPin, MonitorPlay, Users } from "lucide-react";
import type { MouseEvent } from "react";
import { Avatar } from "@/components/common/Avatar";
import { Badge } from "@/components/common/Feedback";
import type { AnnouncementCard as Card } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDateTime, formatDay, formatMonth } from "@/utils/format";
import { activityTypeLabels } from "@/utils/labels";

const coverTones = ["from-teal-600 to-emerald-500", "from-sky-600 to-cyan-500", "from-amber-500 to-orange-400", "from-violet-600 to-fuchsia-500", "from-slate-700 to-slate-500"];

function toneFor(seed: string) {
  let h = 0;
  for (const c of seed) h = (h * 33 + c.charCodeAt(0)) | 0;
  return coverTones[Math.abs(h) % coverTones.length];
}

export function ActivityIcon({ type, className }: { type: Card["activity_type"]; className?: string }) {
  const Icon = type === "online" ? MonitorPlay : type === "hybrid" ? Globe2 : MapPin;
  return <Icon className={className} />;
}

export function StatusBadge({ status }: { status: Card["status"] }) {
  if (status === "published") return null;
  return <Badge tone={status === "draft" ? "warning" : "neutral"}>{status === "draft" ? "Draft" : "Archived"}</Badge>;
}

/** Announcement card used on the landing page and in the authenticated list. */
export function AnnouncementCard({ announcement: a, onOpen, onToggleBookmark, showAuthor = true, bookmarkPending }: {
  announcement: Card; onOpen: () => void; onToggleBookmark?: () => void; showAuthor?: boolean; bookmarkPending?: boolean;
}) {
  const stop = (e: MouseEvent) => {
    e.stopPropagation();
    onToggleBookmark?.();
  };
  return (
    <article
      onClick={onOpen}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen())}
      role="link"
      tabIndex={0}
      aria-label={a.title}
      className="card group flex cursor-pointer flex-col overflow-hidden transition duration-200 hover:-translate-y-0.5 hover:shadow-pop"
    >
      <div className="relative aspect-[16/8] overflow-hidden">
        {a.cover_image ? (
          <img src={a.cover_image} alt="" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" loading="lazy" />
        ) : (
          <div className={cn("flex h-full w-full items-end bg-gradient-to-br p-4", toneFor(a.category?.slug ?? a.id))}>
            <span className="text-sm font-semibold tracking-wide text-white/90">{a.category?.name ?? "Announcement"}</span>
          </div>
        )}
        {a.start_datetime && (
          <div className="absolute top-3 left-3 flex w-12 flex-col items-center rounded-xl bg-white/95 py-1.5 shadow-sm">
            <span className="text-[10px] font-semibold text-rose-600 uppercase">{formatMonth(a.start_datetime)}</span>
            <span className="text-lg leading-none font-bold text-slate-900">{formatDay(a.start_datetime)}</span>
          </div>
        )}
        {onToggleBookmark && (
          <button
            onClick={stop}
            disabled={bookmarkPending}
            aria-pressed={a.is_bookmarked}
            aria-label={a.is_bookmarked ? "Remove bookmark" : "Bookmark"}
            className="absolute top-3 right-3 rounded-full bg-white/95 p-2 text-slate-700 shadow-sm transition hover:text-brand-700 disabled:opacity-60"
          >
            {a.is_bookmarked ? <BookmarkCheck className="h-4 w-4 fill-brand-600 text-brand-700" /> : <Bookmark className="h-4 w-4" />}
          </button>
        )}
      </div>
      <div className="flex flex-1 flex-col p-5">
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          {a.category && <Badge tone="brand">{a.category.name}</Badge>}
          <Badge icon={<ActivityIcon type={a.activity_type} className="h-3 w-3" />}>{activityTypeLabels[a.activity_type]}</Badge>
          {a.visibility === "members_only" && <Badge tone="info" icon={<Users className="h-3 w-3" />}>Members</Badge>}
          {a.visibility === "private" && <Badge icon={<Lock className="h-3 w-3" />}>Private</Badge>}
          <StatusBadge status={a.status} />
        </div>
        <h3 className="line-clamp-2 text-[17px] leading-snug font-semibold text-slate-900 group-hover:text-brand-800">{a.title}</h3>
        {a.short_description && <p className="mt-1.5 line-clamp-2 text-sm text-slate-600">{a.short_description}</p>}
        <div className="mt-4 space-y-1.5 text-sm text-slate-500">
          {a.start_datetime && (
            <p className="flex items-center gap-2"><CalendarDays className="h-4 w-4 shrink-0" />{formatDateTime(a.start_datetime)}</p>
          )}
          {a.location && <p className="flex items-center gap-2 truncate"><MapPin className="h-4 w-4 shrink-0" /><span className="truncate">{a.location}</span></p>}
        </div>
        {showAuthor && (
          <div className="mt-auto flex items-center gap-2 pt-4">
            <Avatar src={a.author.profile_picture} name={a.author.full_name} size="xs" />
            <span className="truncate text-xs text-slate-500">
              {a.organizer_name ? <>by <span className="font-medium text-slate-700">{a.organizer_name}</span></> : <>posted by <span className="font-medium text-slate-700">{a.author.full_name}</span></>}
            </span>
          </div>
        )}
      </div>
    </article>
  );
}

export function AnnouncementCardSkeleton() {
  return (
    <div className="card overflow-hidden" aria-hidden>
      <div className="aspect-[16/8] animate-pulse bg-slate-200/70" />
      <div className="space-y-2.5 p-5">
        <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200/70" />
        <div className="h-5 w-4/5 animate-pulse rounded bg-slate-200/70" />
        <div className="h-3.5 w-full animate-pulse rounded bg-slate-200/70" />
        <div className="h-3.5 w-2/3 animate-pulse rounded bg-slate-200/70" />
      </div>
    </div>
  );
}
