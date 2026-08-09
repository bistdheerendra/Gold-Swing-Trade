/**
 * Exponential Moving Average — causal only (no look-ahead).
 * EMA[i] uses closes[0..i] exclusively.
 */

export const DEFAULT_EMA_PERIODS = [20, 50, 100, 200] as const;

export type EmaPeriod = (typeof DEFAULT_EMA_PERIODS)[number];

/**
 * Compute EMA for a close series.
 * Warm-up: SMA of the first `period` closes, then recursive EMA.
 * Indices before `period - 1` are `null` (insufficient history).
 */
export function computeEma(
  closes: readonly number[],
  period: number,
): Array<number | null> {
  if (period < 1) {
    throw new Error(`EMA period must be >= 1, got ${period}`);
  }
  const out: Array<number | null> = Array(closes.length).fill(null);
  if (closes.length < period) {
    return out;
  }

  let sum = 0;
  for (let i = 0; i < period; i += 1) {
    sum += closes[i]!;
  }
  let ema = sum / period;
  out[period - 1] = ema;

  const alpha = 2 / (period + 1);
  for (let i = period; i < closes.length; i += 1) {
    ema = alpha * closes[i]! + (1 - alpha) * ema;
    out[i] = ema;
  }
  return out;
}

export function computeEmaBundle(
  closes: readonly number[],
  periods: readonly number[] = DEFAULT_EMA_PERIODS,
): Record<number, Array<number | null>> {
  const bundle: Record<number, Array<number | null>> = {};
  for (const period of periods) {
    bundle[period] = computeEma(closes, period);
  }
  return bundle;
}
