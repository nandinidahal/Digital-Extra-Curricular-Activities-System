import { useState } from "react";
import { cn } from "@/utils/cn";
import { initials } from "@/utils/format";

const sizes = { xs: "h-7 w-7 text-[10px]", sm: "h-9 w-9 text-xs", md: "h-11 w-11 text-sm", lg: "h-16 w-16 text-lg", xl: "h-28 w-28 text-3xl" };
const palette = ["bg-teal-100 text-teal-800", "bg-amber-100 text-amber-800", "bg-sky-100 text-sky-800", "bg-rose-100 text-rose-800", "bg-violet-100 text-violet-800", "bg-lime-100 text-lime-800"];

function colorFor(seed: string) {
  let hash = 0;
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

export function Avatar({ src, name, size = "md", className, online }: {
  src?: string | null; name?: string | null; size?: keyof typeof sizes; className?: string; online?: boolean | null;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <span className={cn("relative inline-flex shrink-0", className)}>
      {src && !failed ? (
        <img src={src} alt={name ? `${name}'s profile picture` : ""} onError={() => setFailed(true)} className={cn("rounded-full object-cover ring-2 ring-white", sizes[size])} loading="lazy" />
      ) : (
        <span aria-hidden className={cn("inline-flex items-center justify-center rounded-full font-semibold ring-2 ring-white", sizes[size], colorFor(name ?? "?"))}>
          {initials(name)}
        </span>
      )}
      {online && <span className="absolute right-0 bottom-0 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-white" aria-label="Online" />}
    </span>
  );
}
