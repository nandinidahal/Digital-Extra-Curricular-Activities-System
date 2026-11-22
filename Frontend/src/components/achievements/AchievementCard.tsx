import { Award, BadgeCheck, Building2, CalendarDays, Clock, Globe2, Lock, Star, Users, XCircle, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar } from "@/components/common/Avatar";
import { Badge } from "@/components/common/Feedback";
import type { Achievement, VerificationStatus, Visibility } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";
import { achievementTypeLabels, levelLabels, verificationLabels, visibilityLabels } from "@/utils/labels";

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const map = {
    verified: { tone: "success", icon: <BadgeCheck className="h-3.5 w-3.5" /> },
    pending: { tone: "warning", icon: <Clock className="h-3.5 w-3.5" /> },
    rejected: { tone: "danger", icon: <XCircle className="h-3.5 w-3.5" /> },
    more_information_required: { tone: "info", icon: <AlertCircle className="h-3.5 w-3.5" /> },
  } as const;
  return <Badge tone={map[status].tone} icon={map[status].icon}>{verificationLabels[status]}</Badge>;
}

export function VisibilityBadge({ visibility }: { visibility: Visibility }) {
  const Icon = visibility === "public" ? Globe2 : visibility === "members_only" ? Users : Lock;
  return <Badge icon={<Icon className="h-3 w-3" />}>{visibilityLabels[visibility]}</Badge>;
}

const levelTone: Record<Achievement["level"], string> = {
  international: "from-violet-600 to-indigo-500",
  national: "from-brand-700 to-brand-500",
  local: "from-sky-600 to-cyan-500",
  institutional: "from-amber-500 to-orange-400",
  other: "from-slate-600 to-slate-400",
};

/** Certificate-style card. Evidence files are private, so cards never show them. */
export function AchievementCard({ achievement: a, showUser = false, showStatus = false }: { achievement: Achievement; showUser?: boolean; showStatus?: boolean }) {
  return (
    <Link to={`/achievements/${a.id}`} className="card group flex flex-col overflow-hidden transition duration-200 hover:-translate-y-0.5 hover:shadow-pop">
      <div className={cn("relative flex h-28 items-end justify-between bg-gradient-to-br p-4 text-white", levelTone[a.level])}>
        <div className="absolute inset-y-0 right-6 w-16 bg-white/10" aria-hidden />
        <div className="relative">
          <p className="text-[11px] font-semibold tracking-widest uppercase opacity-90">{levelLabels[a.level]} · {achievementTypeLabels[a.achievement_type]}</p>
          {a.position && <p className="mt-0.5 text-lg font-bold">{a.position}</p>}
        </div>
        <span className="relative flex h-12 w-12 items-center justify-center rounded-full bg-white/95 text-brand-800 shadow">
          <Award className="h-6 w-6" />
        </span>
        {a.is_featured && <span className="absolute top-3 left-3 inline-flex items-center gap-1 rounded-full bg-accent-400 px-2 py-0.5 text-[11px] font-semibold text-amber-950"><Star className="h-3 w-3 fill-current" /> Featured</span>}
      </div>
      <div className="flex flex-1 flex-col p-4">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {(showStatus || a.verification_status === "verified") && <VerificationBadge status={a.verification_status} />}
          {a.category && <Badge tone="brand">{a.category.name}</Badge>}
          {showStatus && <VisibilityBadge visibility={a.visibility} />}
        </div>
        <h3 className="line-clamp-2 font-semibold text-slate-900 group-hover:text-brand-800">{a.title}</h3>
        <div className="mt-2 space-y-1 text-sm text-slate-500">
          {a.organization && <p className="flex items-center gap-2 truncate"><Building2 className="h-4 w-4 shrink-0" /><span className="truncate">{a.organization}</span></p>}
          <p className="flex items-center gap-2"><CalendarDays className="h-4 w-4 shrink-0" />{formatDate(a.achievement_date)}</p>
        </div>
        {a.skills.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {a.skills.slice(0, 4).map((s) => <span key={s} className="chip bg-slate-100 text-slate-600">{s}</span>)}
            {a.skills.length > 4 && <span className="chip bg-slate-100 text-slate-500">+{a.skills.length - 4}</span>}
          </div>
        )}
        {showUser && (
          <div className="mt-auto flex items-center gap-2 pt-4">
            <Avatar src={a.user.profile_picture} name={a.user.full_name} size="xs" />
            <span className="truncate text-xs font-medium text-slate-600">{a.user.full_name}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
