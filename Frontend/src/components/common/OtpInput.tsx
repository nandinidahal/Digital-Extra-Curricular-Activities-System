import { useId } from "react";
import { cn } from "@/utils/cn";

/** One accessible input for a 6-digit code (paste-friendly, numeric keypad on phones). */
export function OtpInput({ value, onChange, error, label = "Verification code" }: {
  value: string; onChange: (value: string) => void; error?: string; label?: string;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        placeholder="••••••"
        aria-invalid={!!error || undefined}
        className={cn("input h-14 text-center font-mono text-2xl tracking-[0.6em]", error && "input-invalid")}
      />
      {error && <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600">{error}</p>}
    </div>
  );
}
