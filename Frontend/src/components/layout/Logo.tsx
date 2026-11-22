import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";

export function Logo({ to = "/", compact, className }: { to?: string; compact?: boolean; className?: string }) {
  return (
    <Link to={to} className={cn("group inline-flex items-center gap-2.5", className)} aria-label="DEAS home">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-brand-700 text-white shadow-sm transition group-hover:bg-brand-800">
        <span className="text-[15px] font-bold tracking-tight">D</span>
        <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-accent-400 ring-2 ring-white" />
      </span>
      {!compact && (
        <span className="leading-none">
          <span className="block text-[17px] font-bold tracking-tight text-slate-900">DEAS</span>
          <span className="hidden text-[10.5px] font-medium tracking-wide text-slate-500 sm:block">Screen Time → Life Time</span>
        </span>
      )}
    </Link>
  );
}
