/** Trading session tagging — definitions from GET /api/market/sessions.

Phase 11.10.1: London/NY use local clocks + IANA timezones so historical
candles pick the DST rules for *that* candle's date (Intl / host TZ DB),
not today's fixed UTC minutes alone.
*/

export type SessionId = "asia" | "london" | "new_york" | "london_ny_overlap";

export type WindowMode = "fixed_utc" | "local" | "overlap";

export type SessionDefinition = {
  id: SessionId | string;
  name: string;
  ist_window: string;
  utc_start_minute: number;
  utc_end_minute: number;
  utc_window: string;
  behavior: string;
  color: string;
  emoji: string;
  chart_fill: string;
  priority: number;
  window_mode?: WindowMode | string;
  timezone?: string | null;
  local_start_minute?: number | null;
  local_end_minute?: number | null;
};

/** Intraday TFs where session bands are meaningful (must match backend). */
export const SESSION_BAND_TIMEFRAMES = new Set(["15m", "30m", "1h"]);

export function supportsSessionBands(timeframe: string): boolean {
  return SESSION_BAND_TIMEFRAMES.has(timeframe.trim().toLowerCase());
}

export function minuteOfDayUtc(date: Date): number {
  return date.getUTCHours() * 60 + date.getUTCMinutes();
}

function inWindow(minute: number, start: number, end: number): boolean {
  if (end <= 1440) return minute >= start && minute < end;
  return minute >= start || minute < end - 1440;
}

/** Local minute-of-day in an IANA zone for a UTC instant (DST-aware via Intl). */
export function minuteOfDayInTimeZone(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(date);
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? "0");
  return hour * 60 + minute;
}

function matchesDefinition(date: Date, def: SessionDefinition): boolean {
  const mode = def.window_mode ?? "fixed_utc";
  if (mode === "local") {
    if (
      !def.timezone ||
      def.local_start_minute == null ||
      def.local_end_minute == null
    ) {
      return false;
    }
    const localMinute = minuteOfDayInTimeZone(date, def.timezone);
    return inWindow(localMinute, def.local_start_minute, def.local_end_minute);
  }
  if (mode === "overlap") {
    // Derived: handled after scanning London + NY
    return false;
  }
  // fixed_utc (Asia) — or legacy payloads without window_mode
  return inWindow(minuteOfDayUtc(date), def.utc_start_minute, def.utc_end_minute);
}

/**
 * Tag a UTC instant using definitions from the sessions API.
 * Overlap = London ∩ New York for that instant (DST-aware via local mode).
 */
export function sessionsForTimestamp(
  isoOrDate: string | Date,
  definitions: readonly SessionDefinition[],
): string[] {
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return [];

  const matched: string[] = [];
  let london = false;
  let ny = false;

  for (const def of definitions) {
    const mode = def.window_mode ?? "fixed_utc";
    if (mode === "overlap") continue;
    if (!matchesDefinition(date, def)) continue;
    matched.push(def.id);
    if (def.id === "london") london = true;
    if (def.id === "new_york") ny = true;
  }

  if (london && ny) {
    const overlap = definitions.find((d) => d.id === "london_ny_overlap");
    if (overlap) matched.push(overlap.id);
  }

  return matched;
}

export function dominantSessionId(
  sessionIds: readonly string[],
  definitions: readonly SessionDefinition[],
): string | null {
  if (!sessionIds.length) return null;
  const byId = new Map(definitions.map((d) => [d.id, d]));
  let best: string | null = null;
  let bestPriority = -1;
  for (const id of sessionIds) {
    const p = byId.get(id)?.priority ?? 0;
    if (p > bestPriority) {
      bestPriority = p;
      best = id;
    }
  }
  return best;
}

export function chartFillForSessions(
  sessionIds: readonly string[],
  definitions: readonly SessionDefinition[],
): string | null {
  const dominant = dominantSessionId(sessionIds, definitions);
  if (!dominant) return null;
  return definitions.find((d) => d.id === dominant)?.chart_fill ?? null;
}
