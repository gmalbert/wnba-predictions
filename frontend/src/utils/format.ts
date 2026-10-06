/** Shared formatting helpers (used by multiple pages). */

export const WNBA_RED = "#C8102E";
export const WNBA_BLUE = "#1D428A";
export const CONF_COLORS: Record<string, string> = {
  High: "#16a34a",
  Medium: "#d97706",
  Low: "#6b7280",
};

export function pct(value: number | null | undefined, digits = 1, fallback = "—") {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 1, fallback = "—") {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value.toFixed(digits);
}

export function signed(value: number | null | undefined, digits = 1, fallback = "—") {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  const v = value.toFixed(digits);
  return value > 0 ? `+${v}` : v;
}

export function int(value: number | null | undefined, fallback = "—") {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value.toLocaleString();
}

/** Short timezone abbreviation for the browser ("EDT", "PDT", "GMT+5:30"). */
export function timeZoneLabel(date: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", { timeZoneName: "short" }).formatToParts(date);
    return parts.find((p) => p.type === "timeZoneName")?.value ?? "";
  } catch {
    return "";
  }
}

export function formatGameTime(scheduledStart: string | null): string {
  if (!scheduledStart) return "";
  const date = new Date(scheduledStart);
  if (Number.isNaN(date.getTime())) return scheduledStart;
  // No explicit timeZone: Intl defaults to the browser's zone, matching the
  // browser-timezone probe in utils/browser_tz.py on the Streamlit side.
  // Locale stays en-US so the wording matches pages/1_Game_Predictions.py.
  // Format: "{Weekday}, {Mon} {DD} · {HH}:{MM} {AM/PM} {TZ}"
  const parts = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const zone = timeZoneLabel(date);
  return `${get("weekday")}, ${get("month")} ${get("day")} · ${get("hour")}:${get("minute")} ${get("dayPeriod")}${zone ? ` ${zone}` : ""}`;
}

export function formatToday(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "2-digit",
    year: "numeric",
  });
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function ageHours(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return (Date.now() - date.getTime()) / 36e5;
}

export function classifyStatus(ok: boolean | undefined | null): string {
  if (ok === true) return "Healthy";
  if (ok === false) return "Failed";
  return "Unknown";
}

export function statusVariant(value: string): "success" | "warning" | "error" | "info" {
  switch (value) {
    case "production_ready":
      return "success";
    case "limited_paper":
      return "warning";
    case "shadow_only":
    case "missing":
      return "error";
    default:
      return "info";
  }
}