import type { HistogramData, UTCTimestamp } from "lightweight-charts";
import type { OHLCVBar } from "./api";
import { toChartTime } from "./chartData";
import {
  chartFillForSessions,
  sessionsForTimestamp,
  type SessionDefinition,
} from "./sessions";

export type SessionHistogramPoint = HistogramData<UTCTimestamp>;

/**
 * Build per-bar histogram colors for session background bands.
 * Uses definitions from GET /api/market/sessions (single source of truth).
 */
export function barsToSessionHistogram(
  bars: readonly OHLCVBar[],
  definitions: readonly SessionDefinition[],
): SessionHistogramPoint[] {
  if (!definitions.length) return [];
  const points: SessionHistogramPoint[] = [];
  for (const bar of bars) {
    const ids = sessionsForTimestamp(bar.timestamp, definitions);
    const color = chartFillForSessions(ids, definitions);
    if (!color) continue;
    points.push({
      time: toChartTime(bar.timestamp),
      value: 1,
      color,
    });
  }
  return points;
}
