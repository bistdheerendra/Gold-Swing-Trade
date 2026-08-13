import type { OHLCVBar } from "./api";

/** Merge a live ticker last price into the forming (last) candle. */
export function applyLivePriceToBars(
  bars: readonly OHLCVBar[],
  price: number | null | undefined,
): OHLCVBar[] {
  if (!bars.length || price == null || !Number.isFinite(price)) {
    return bars.length ? [...bars] : [];
  }
  const next = bars.slice();
  const last = { ...next[next.length - 1]! };
  last.close = price;
  last.high = Math.max(last.high, price);
  last.low = Math.min(last.low, price);
  next[next.length - 1] = last;
  return next;
}
