import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { toast } from "sonner";
import { errorMessage, toApiError } from "@/services/api/errors";

/**
 * Put backend field errors (400 validation_error) on the matching form fields; anything that
 * does not belong to a visible field becomes a toast. Returns true when errors were applied.
 */
export function applyServerErrors<T extends FieldValues>(error: unknown, setError: UseFormSetError<T>, fields: readonly string[]): boolean {
  const e = toApiError(error);
  let applied = false;
  const leftovers: string[] = [];
  for (const [field, messages] of Object.entries(e.fieldErrors)) {
    if (fields.includes(field)) {
      setError(field as Path<T>, { type: "server", message: messages[0] });
      applied = true;
    } else {
      leftovers.push(messages[0]);
    }
  }
  if (leftovers.length) toast.error(leftovers[0]);
  else if (!applied) toast.error(errorMessage(error));
  return applied;
}

export function passwordStrength(password: string): { score: 0 | 1 | 2 | 3 | 4; label: string } {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score++;
  if (/^\d+$/.test(password)) score = Math.min(score, 1);
  const labels = ["Too weak", "Weak", "Fair", "Good", "Strong"];
  return { score: score as 0 | 1 | 2 | 3 | 4, label: labels[score] };
}
