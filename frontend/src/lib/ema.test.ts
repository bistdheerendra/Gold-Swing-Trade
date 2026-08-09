import { describe, expect, it } from "vitest";
import { computeEma, computeEmaBundle } from "./ema";

describe("computeEma", () => {
  it("returns nulls until warm-up completes", () => {
    const closes = [1, 2, 3, 4, 5];
    const ema = computeEma(closes, 3);
    expect(ema[0]).toBeNull();
    expect(ema[1]).toBeNull();
    expect(ema[2]).toBeCloseTo(2); // SMA(1,2,3)
  });

  it("is causal — extending series does not change earlier values", () => {
    const base = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19];
    const emaShort = computeEma(base, 4);
    const emaLong = computeEma([...base, 20, 21], 4);
    for (let i = 0; i < base.length; i += 1) {
      expect(emaLong[i]).toEqual(emaShort[i]);
    }
  });

  it("does not use future closes (manual step check)", () => {
    const closes = [100, 102, 101, 103, 104];
    const period = 3;
    const ema = computeEma(closes, period);
    // At index 3, EMA must equal alpha*103 + (1-alpha)*ema[2]
    const alpha = 2 / (period + 1);
    const expected = alpha * 103 + (1 - alpha) * (ema[2] as number);
    expect(ema[3]).toBeCloseTo(expected, 10);
  });

  it("builds default EMA bundle periods", () => {
    const closes = Array.from({ length: 250 }, (_, i) => 2000 + i * 0.1);
    const bundle = computeEmaBundle(closes);
    expect(Object.keys(bundle).map(Number).sort((a, b) => a - b)).toEqual([
      20, 50, 100, 200,
    ]);
    expect(bundle[20]![19]).not.toBeNull();
    expect(bundle[200]![199]).not.toBeNull();
    expect(bundle[200]![198]).toBeNull();
  });
});
