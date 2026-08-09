import type { CandlestickData, LineData, UTCTimestamp } from "lightweight-charts";
import type { OHLCVBar } from "./api";
import { computeEma, DEFAULT_EMA_PERIODS, type EmaPeriod } from "./ema";

export type ChartCandle = CandlestickData<UTCTimestamp>;
export type ChartLinePoint = LineData<UTCTimestamp>;

export function toUnixSeconds(iso: string): UTCTimestamp {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) {
    throw new Error(`Invalid timestamp: ${iso}`);
  }
  return Math.floor(ms / 1000) as UTCTimestamp;
}

export function barsToCandles(bars: readonly OHLCVBar[]): ChartCandle[] {
  return bars.map((bar) => ({
    time: toUnixSeconds(bar.timestamp),
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
        time: toUnixSeconds(bars[i]!.timestamp),
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
