import { FileText, ImagePlus, X } from "lucide-react";
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { toast } from "sonner";
import { cn } from "@/utils/cn";
import { formatBytes } from "@/utils/format";

/** Multi-file picker with previews. `validate` returns an error message or null per file. */
export function FilePicker({ files, onChange, accept, max, validate, label = "Add files", compact, icon }: {
  files: File[]; onChange: (files: File[]) => void; accept: string; max: number;
  validate: (file: File) => string | null; label?: string; compact?: boolean; icon?: ReactNode;
}) {
  const input = useRef<HTMLInputElement>(null);
  const previews = useMemo(() => files.map((f) => (f.type.startsWith("image/") ? URL.createObjectURL(f) : null)), [files]);
  useEffect(() => () => previews.forEach((p) => p && URL.revokeObjectURL(p)), [previews]);

  const add = (list: FileList | null) => {
    if (!list) return;
    const next = [...files];
    for (const file of Array.from(list)) {
      if (next.length >= max) {
        toast.error(`You can attach at most ${max} file${max === 1 ? "" : "s"}.`);
        break;
      }
      const problem = validate(file);
      if (problem) toast.error(problem);
      else next.push(file);
    }
    onChange(next);
    if (input.current) input.current.value = "";
  };

  return (
    <div>
      {files.length > 0 && (
        <div className={cn("mb-3 grid gap-2", compact ? "grid-cols-4 sm:grid-cols-6" : "grid-cols-3 sm:grid-cols-4")}>
          {files.map((file, i) => (
            <div key={`${file.name}-${i}`} className="group relative aspect-square overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
              {previews[i] ? (
                <img src={previews[i]!} alt={file.name} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-1 p-2 text-center">
                  <FileText className="h-6 w-6 text-slate-400" />
                  <span className="line-clamp-2 text-[11px] text-slate-600">{file.name}</span>
                  <span className="text-[10px] text-slate-400">{formatBytes(file.size)}</span>
                </div>
              )}
              <button
                type="button"
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="absolute top-1 right-1 rounded-full bg-slate-900/70 p-1 text-white opacity-90 hover:bg-slate-900"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      {files.length < max && (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className={cn(
            "inline-flex items-center gap-2 rounded-xl text-sm font-medium text-brand-700 transition hover:bg-brand-50",
            compact ? "px-2.5 py-1.5" : "w-full justify-center border border-dashed border-brand-300 px-4 py-6",
          )}
        >
          {icon ?? <ImagePlus className="h-4 w-4" />}
          {label}
        </button>
      )}
      <input ref={input} type="file" accept={accept} multiple={max > 1} className="sr-only" tabIndex={-1} onChange={(e) => add(e.target.files)} />
    </div>
  );
}
