import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format } from "date-fns";
import { TZDate } from "@date-fns/tz";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const DEFAULT_TZ = "UTC";

/**
 * Parse API date string as UTC when it has no timezone (backend sends naive UTC).
 * Returns ISO string with Z for use with TZDate.
 */
function toUtcIso(date: string): string {
  const s = typeof date === "string" ? date.trim() : "";
  if (!s) return "";
  if (/[Zz]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) return s;
  return s + "Z";
}

/**
 * Get a TZDate for the given UTC moment in the given timezone (or system default).
 */
function inTz(date: string, timeZone: string = DEFAULT_TZ): TZDate {
  const iso = toUtcIso(date);
  return timeZone ? new TZDate(iso, timeZone) : new TZDate(iso);
}

/**
 * Format an ISO date string for display (date + time).
 * @param date - ISO date string (stored as UTC; naive strings treated as UTC).
 * @param timeZone - IANA timezone (e.g. 'UTC', 'America/New_York'). Omit for browser local.
 * @param hour12 - true = 12-hour (AM/PM), false = 24-hour. Omit for locale default.
 */
export function formatDate(date: string, timeZone?: string, hour12?: boolean): string {
  const tz = timeZone ?? DEFAULT_TZ;
  const d = inTz(date, tz);
  const use12 = hour12 ?? true;
  return format(d, use12 ? "MMM d, yyyy h:mm a" : "MMM d, yyyy HH:mm");
}

/**
 * Format time only (hour:minute) from an ISO date string.
 * @param date - ISO date string (stored as UTC).
 * @param timeZone - IANA timezone (optional).
 * @param hour12 - true = 12-hour (AM/PM), false = 24-hour (optional).
 */
export function formatTime(date: string, timeZone?: string, hour12?: boolean): string {
  const tz = timeZone ?? DEFAULT_TZ;
  const d = inTz(date, tz);
  const use12 = hour12 ?? true;
  return format(d, use12 ? "h:mm a" : "HH:mm");
}

/**
 * Format date only (no time) from an ISO date string.
 * @param date - ISO date string (stored as UTC).
 * @param timeZone - IANA timezone (optional).
 */
export function formatDateOnly(date: string, timeZone?: string): string {
  const tz = timeZone ?? DEFAULT_TZ;
  const d = inTz(date, tz);
  return format(d, "MMM d, yyyy");
}

/**
 * Format relative time or fall back to full date.
 * @param date - ISO date string (stored as UTC).
 * @param timeZone - IANA timezone (optional).
 * @param hour12 - true = 12-hour, false = 24-hour (optional).
 */
export function formatRelativeTime(date: string, timeZone?: string, hour12?: boolean): string {
  const now = new Date();
  const iso = toUtcIso(date);
  const then = new Date(iso || NaN);
  const diffInSeconds = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (diffInSeconds < 60) return "just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return formatDate(date, timeZone, hour12);
}
