import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "@/services/api/errors";
import { cn } from "@/utils/cn";
import { Button } from "./Button";

export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn("inline-flex items-center gap-2 text-slate-500", className)}>
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-slate-200/70", className)} aria-hidden />;
}

export function CardSkeleton({ lines = 3, media = false }: { lines?: number; media?: boolean }) {
  return (
    <div className="card p-5" aria-hidden>
      <div className="flex items-center gap-3">
        <Skeleton className="h-11 w-11 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-1/3" />
          <Skeleton className="h-3 w-1/4" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn("h-3.5", i === lines - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
      {media && <Skeleton className="mt-4 h-48 w-full rounded-xl" />}
    </div>
  );
}

export function EmptyState({ icon, title, description, action, className }: {
  icon?: ReactNode; title: string; description?: ReactNode; action?: ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center", className)}>
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-700">
        {icon ?? <Inbox className="h-6 w-6" />}
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Something went wrong", className }: {
  error?: unknown; onRetry?: () => void; title?: string; className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center rounded-2xl border border-rose-200 bg-rose-50/60 px-6 py-10 text-center", className)}>
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {error !== undefined && <p className="mt-1 max-w-md text-sm text-slate-600">{errorMessage(error)}</p>}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" icon={<RefreshCw className="h-4 w-4" />} onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

const badgeTones = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-800",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-rose-50 text-rose-700",
  info: "bg-sky-50 text-sky-700",
};

export function Badge({ tone = "neutral", icon, children, className }: {
  tone?: keyof typeof badgeTones; icon?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <span className={cn("chip", badgeTones[tone], className)}>
      {icon}
      {children}
    </span>
  );
}

export function CountBadge({ count, className }: { count: number; className?: string }) {
  if (!count) return null;
  return (
    <span className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 text-[11px] font-semibold text-white", className)}>
      {count > 99 ? "99+" : count}
    </span>
  );
}
