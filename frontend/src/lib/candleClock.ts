/** Candle open/close clock helpers for live chart countdown. */

import type { Timeframe } from "./api";

const TF_MS: Record<string, number> = {
  "1m": 60_000,
  "5m": 5 * 60_000,
  "15m": 15 * 60_000,
  "30m": 30 * 60_000,
  "1h": 60 * 60_000,
  "4h": 4 * 60 * 60_000,
  "1d": 24 * 60 * 60_000,
};

export function timeframeDurationMs(timeframe: string | Timeframe): number | null {
  return TF_MS[String(timeframe).trim().toLowerCase()] ?? null;
}

/** Floor `now` to the open time of the active candle (UTC). */
export function candleOpenMs(
  timeframe: string | Timeframe,
  nowMs: number = Date.now(),
): number | null {
  const dur = timeframeDurationMs(timeframe);
  if (dur == null || !Number.isFinite(nowMs)) return null;
  return Math.floor(nowMs / dur) * dur;
}

export function candleCloseMs(
  timeframe: string | Timeframe,
  nowMs: number = Date.now(),
): number | null {
  const open = candleOpenMs(timeframe, nowMs);
  const dur = timeframeDurationMs(timeframe);
  if (open == null || dur == null) return null;
  return open + dur;
}

export function msUntilCandleClose(
  timeframe: string | Timeframe,
  nowMs: number = Date.now(),
): number | null {
  const close = candleCloseMs(timeframe, nowMs);
  if (close == null) return null;
  return Math.max(0, close - nowMs);
}

/** Format remaining ms as HH:MM:SS or MM:SS. */
export function formatCountdown(ms: number | null): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "—";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) return `${h}:${mm}:${ss}`;
  return `${mm}:${ss}`;
}

export type CandleClock = {
  openMs: number;
  closeMs: number;
  remainingMs: number;
  label: string;
  progress: number; // 0..1 elapsed within candle
};

export function getCandleClock(
  timeframe: string | Timeframe,
  nowMs: number = Date.now(),
): CandleClock | null {
  const openMs = candleOpenMs(timeframe, nowMs);
  const closeMs = candleCloseMs(timeframe, nowMs);
  const dur = timeframeDurationMs(timeframe);
  if (openMs == null || closeMs == null || dur == null) return null;
  const remainingMs = Math.max(0, closeMs - nowMs);
  const elapsed = Math.min(dur, Math.max(0, nowMs - openMs));
  return {
    openMs,
    closeMs,
    remainingMs,
    label: formatCountdown(remainingMs),
    progress: elapsed / dur,
  };
}
