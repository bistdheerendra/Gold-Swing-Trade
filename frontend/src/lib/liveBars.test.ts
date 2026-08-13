import { describe, expect, it } from "vitest";
import type { OHLCVBar } from "./api";
import { applyLivePriceToBars } from "./liveBars";

function sample(): OHLCVBar[] {
  return [
    {
      timestamp: "2024-01-01T12:00:00.000Z",
      symbol: "PAXGUSD",
      timeframe: "1h",
      open: 100,
      high: 101,
      low: 99,
      close: 100.5,
      volume: 10,
      source: "test",
    },
  ];
}

describe("applyLivePriceToBars", () => {
  it("updates close/high/low on the forming candle", () => {
    const out = applyLivePriceToBars(sample(), 102);
    expect(out[0]!.close).toBe(102);
    expect(out[0]!.high).toBe(102);
    expect(out[0]!.open).toBe(100);
  });

  it("extends low when price drops", () => {
    const out = applyLivePriceToBars(sample(), 98);
    expect(out[0]!.close).toBe(98);
    expect(out[0]!.low).toBe(98);
  });

  it("ignores invalid prices", () => {
    const bars = sample();
    expect(applyLivePriceToBars(bars, null)[0]!.close).toBe(100.5);
  });
});
