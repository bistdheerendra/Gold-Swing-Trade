import type { CandlestickData, LineData, UTCTimestamp } from "lightweight-charts";
import type { OHLCVBar } from "./api";
import { computeEma, DEFAULT_EMA_PERIODS, type EmaPeriod } from "./ema";

export type ChartCandle = CandlestickData<UTCTimestamp>;
export type ChartLinePoint = LineData<UTCTimestamp>;

/** Chart display timezone (Delta India / PAXGUSD). */
export const CHART_TIMEZONE = "Asia/Kolkata";

/** IST is fixed UTC+5:30 (no DST). LWC shows UTC labels, so we shift bar times. */
export const IST_OFFSET_SECONDS = 5 * 60 * 60 + 30 * 60;

export function toUnixSeconds(iso: string): UTCTimestamp {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) {
    throw new Error(`Invalid timestamp: ${iso}`);
  }
  return Math.floor(ms / 1000) as UTCTimestamp;
}

/** Unix seconds shifted so Lightweight Charts' UTC axis reads as IST. */
export function toChartTime(iso: string): UTCTimestamp {
  return (toUnixSeconds(iso) + IST_OFFSET_SECONDS) as UTCTimestamp;
}

/** Undo chart IST shift → real UTC unix seconds. */
export function fromChartTime(chartTime: number): number {
  return chartTime - IST_OFFSET_SECONDS;
}

export function formatIstDateTime(value: string | number | Date | null | undefined): string {
  if (value == null) return "—";
  const date =
    typeof value === "number"
      ? new Date(value * 1000)
      : value instanceof Date
        ? value
        : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: CHART_TIMEZONE,
    day: "2-digit",
    month: "short",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
  return `${formatted} IST`;
}

export function barsToCandles(bars: readonly OHLCVBar[]): ChartCandle[] {
  return bars.map((bar) => ({
    time: toChartTime(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }));
}

export function barsToEmaSeries(
  bars: readonly OHLCVBar[],
  periods: readonly number[] = DEFAULT_EMA_PERIODS,
): Record<number, ChartLinePoint[]> {
  const closes = bars.map((bar) => bar.close);
  const result: Record<number, ChartLinePoint[]> = {};
  for (const period of periods) {
    const ema = computeEma(closes, period);
    const points: ChartLinePoint[] = [];
    for (let i = 0; i < bars.length; i += 1) {
      const value = ema[i];
      if (value == null) continue;
      points.push({
        time: toChartTime(bars[i]!.timestamp),
        value,
      });
    }
    result[period] = points;
  }
  return result;
}

export const EMA_COLORS: Record<EmaPeriod, string> = {
  20: "#f0d78c",
  50: "#7ec8e3",
  100: "#c084fc",
  200: "#f97316",
};

export function formatPrice(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}
