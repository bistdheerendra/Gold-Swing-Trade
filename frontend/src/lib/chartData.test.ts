import { describe, expect, it } from "vitest";
import {
  barsToCandles,
  barsToEmaSeries,
  formatIstDateTime,
  fromChartTime,
  IST_OFFSET_SECONDS,
  toChartTime,
  toUnixSeconds,
} from "./chartData";
import type { OHLCVBar } from "./api";

function bar(i: number, close: number): OHLCVBar {
  return {
    timestamp: new Date(Date.UTC(2024, 0, 1, i)).toISOString(),
    symbol: "PAXGUSD",
    timeframe: "1h",
    open: close - 0.5,
    high: close + 1,
    low: close - 1,
    close,
    volume: 1000,
    source: "test",
  };
}

describe("chartData adapters", () => {
  it("maps bars to candles in chronological unix seconds", () => {
    const bars = [bar(0, 2300), bar(1, 2301)];
    const candles = barsToCandles(bars);
    expect(candles).toHaveLength(2);
    expect(candles[0]!.time).toBeLessThan(candles[1]!.time);
    expect(candles[0]!.close).toBe(2300);
  });

  it("shifts candle times by IST offset for chart axis display", () => {
    const bars = [bar(0, 2300)];
    const utc = toUnixSeconds(bars[0]!.timestamp);
    expect(toChartTime(bars[0]!.timestamp)).toBe(utc + IST_OFFSET_SECONDS);
    expect(barsToCandles(bars)[0]!.time).toBe(utc + IST_OFFSET_SECONDS);
    expect(fromChartTime(utc + IST_OFFSET_SECONDS)).toBe(utc);
  });

  it("formats times in IST", () => {
    // 2024-01-01 00:00 UTC → 05:30 IST
    expect(formatIstDateTime("2024-01-01T00:00:00.000Z")).toMatch(/05:30/);
    expect(formatIstDateTime("2024-01-01T00:00:00.000Z")).toContain("IST");
  });

  it("EMA series omit warm-up points and stay aligned to bar times", () => {
    const bars = Array.from({ length: 30 }, (_, i) => bar(i, 2300 + i));
    const series = barsToEmaSeries(bars, [20]);
    expect(series[20]).toHaveLength(11); // indices 19..29
    expect(series[20]![0]!.time).toBe(barsToCandles(bars)[19]!.time);
  });
});
