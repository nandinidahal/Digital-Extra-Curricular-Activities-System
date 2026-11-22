const dateFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const monthFmt = new Intl.DateTimeFormat(undefined, { month: "short" });
const relFmt = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export const formatDate = (v?: string | null) => (toDate(v) ? dateFmt.format(toDate(v)!) : "");
export const formatDateTime = (v?: string | null) => (toDate(v) ? dateTimeFmt.format(toDate(v)!) : "");
export const formatTime = (v?: string | null) => (toDate(v) ? timeFmt.format(toDate(v)!) : "");
export const formatMonth = (v?: string | null) => (toDate(v) ? monthFmt.format(toDate(v)!) : "");
export const formatDay = (v?: string | null) => (toDate(v) ? String(toDate(v)!.getDate()) : "");

export function timeAgo(value?: string | null): string {
  const d = toDate(value);
  if (!d) return "";
  const seconds = Math.round((d.getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["minute", 60], ["hour", 3600], ["day", 86400], ["week", 604800],
  ];
  for (let i = units.length - 1; i >= 0; i--) {
    const [unit, size] = units[i];
    if (abs >= size) {
      if (unit === "week" && abs > 4 * 604800) return formatDate(value);
      return relFmt.format(Math.round(seconds / size), unit);
    }
  }
  return relFmt.format(Math.round(seconds / 60), "minute");
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** <input type="datetime-local"> value (local time) <-> ISO string with timezone. */
export function toLocalInput(iso?: string | null): string {
  const d = toDate(iso);
  if (!d) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function initials(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}
