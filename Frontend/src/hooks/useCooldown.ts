import { useEffect, useState } from "react";

/** Countdown in seconds (for "resend code" buttons; the backend enforces its own cooldown). */
export function useCooldown(initial = 0) {
  const [seconds, setSeconds] = useState(initial);
  useEffect(() => {
    if (seconds <= 0) return;
    const t = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [seconds]);
  return [seconds, setSeconds] as const;
}
