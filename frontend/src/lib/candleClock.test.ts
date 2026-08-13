import { describe, expect, it } from "vitest";
import {
  candleCloseMs,
  candleOpenMs,
  formatCountdown,
  getCandleClock,
  msUntilCandleClose,
  timeframeDurationMs,
} from "./candleClock";

describe("candleClock", () => {
  it("resolves timeframe durations", () => {
    expect(timeframeDurationMs("15m")).toBe(15 * 60_000);
    expect(timeframeDurationMs("1h")).toBe(60 * 60_000);
    expect(timeframeDurationMs("4h")).toBe(4 * 60 * 60_000);
    expect(timeframeDurationMs("nope")).toBeNull();
  });

  it("floors to UTC candle boundaries", () => {
    // 2024-01-01 12:17:30 UTC → 1h open 12:00, close 13:00
    const now = Date.UTC(2024, 0, 1, 12, 17, 30);
    expect(candleOpenMs("1h", now)).toBe(Date.UTC(2024, 0, 1, 12, 0, 0));
    expect(candleCloseMs("1h", now)).toBe(Date.UTC(2024, 0, 1, 13, 0, 0));
    expect(msUntilCandleClose("1h", now)).toBe(42.5 * 60_000);
  });

  it("formats countdown labels", () => {
    expect(formatCountdown(65_000)).toBe("01:05");
    expect(formatCountdown(3_661_000)).toBe("1:01:01");
    expect(formatCountdown(null)).toBe("—");
  });

  it("reports progress within the candle", () => {
    const now = Date.UTC(2024, 0, 1, 12, 30, 0);
    const clock = getCandleClock("1h", now);
    expect(clock?.progress).toBeCloseTo(0.5, 5);
    expect(clock?.label).toBe("30:00");
  });
});
