import { passwordStrength } from "@/utils/forms";
import { cn } from "@/utils/cn";

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const { score, label } = passwordStrength(password);
  const colors = ["bg-rose-500", "bg-rose-500", "bg-amber-500", "bg-brand-500", "bg-emerald-600"];
  return (
    <div className="mt-2" aria-live="polite">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className={cn("h-1.5 flex-1 rounded-full", i < score ? colors[score] : "bg-slate-200")} />
        ))}
      </div>
      <p className="mt-1 text-xs text-slate-500">Password strength: <span className="font-medium text-slate-700">{label}</span>. Use 8+ characters; avoid common or all-number passwords.</p>
    </div>
  );
}
