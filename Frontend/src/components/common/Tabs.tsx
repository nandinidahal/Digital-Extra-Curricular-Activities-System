import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/utils/cn";

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  count?: number;
  hidden?: boolean;
}

export function Tabs<T extends string>({ items, value, onChange, className }: {
  items: TabItem<T>[]; value: T; onChange: (value: T) => void; className?: string;
}) {
  return (
    <div role="tablist" className={cn("scroll-thin -mx-1 flex gap-1 overflow-x-auto px-1", className)}>
      {items.filter((i) => !i.hidden).map((item) => (
        <button
          key={item.value}
          role="tab"
          type="button"
          aria-selected={value === item.value}
          onClick={() => onChange(item.value)}
          className={cn(
            "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium whitespace-nowrap transition",
            value === item.value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-white hover:text-slate-900",
          )}
        >
          {item.label}
          {!!item.count && <span className={cn("rounded-full px-1.5 text-xs", value === item.value ? "bg-white/20" : "bg-slate-200")}>{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function LinkTabs({ items, className }: { items: { to: string; label: ReactNode; end?: boolean; hidden?: boolean }[]; className?: string }) {
  return (
    <nav className={cn("scroll-thin -mx-1 flex gap-1 overflow-x-auto px-1", className)}>
      {items.filter((i) => !i.hidden).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium whitespace-nowrap transition",
              isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-white hover:text-slate-900",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
