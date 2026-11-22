import { MoreHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/utils/cn";

export interface MenuItem {
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
  danger?: boolean;
  hidden?: boolean;
}

/** Accessible dropdown menu: click/Enter opens, Escape or outside click closes. */
export function Menu({ items, label = "More actions", trigger, align = "right" }: {
  items: MenuItem[]; label?: string; trigger?: ReactNode; align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const visible = items.filter((i) => !i.hidden);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!visible.length) return null;
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
      >
        {trigger ?? <MoreHorizontal className="h-5 w-5" />}
      </button>
      {open && (
        <div role="menu" className={cn("absolute z-30 mt-1 min-w-48 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-pop", align === "right" ? "right-0" : "left-0")}>
          {visible.map((item) => (
            <button
              key={item.label}
              role="menuitem"
              type="button"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={cn("flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm transition hover:bg-slate-50", item.danger ? "text-rose-600" : "text-slate-700")}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
