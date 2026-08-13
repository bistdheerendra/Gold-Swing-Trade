import { useEffect, useState } from "react";
import {
  formatCountdown,
  getCandleClock,
  msUntilCandleClose,
} from "../../lib/candleClock";
import type { Timeframe } from "../../lib/api";

type Props = {
  timeframe: Timeframe | string;
  /** Fires once when the countdown crosses into a new candle. */
  onCandleClose?: () => void;
  className?: string;
};

/**
 * Live countdown to the close of the current OHLCV candle (UTC-aligned).
 */
export function CandleCountdown({ timeframe, onCandleClose, className }: Props) {
  const [label, setLabel] = useState(() =>
    formatCountdown(msUntilCandleClose(timeframe)),
  );
  const [progress, setProgress] = useState(() => {
    const clock = getCandleClock(timeframe);
    return clock?.progress ?? 0;
  });

  useEffect(() => {
    let prevCloseMs = getCandleClock(timeframe)?.closeMs ?? null;

    const tick = () => {
      const clock = getCandleClock(timeframe);
      if (!clock) {
        setLabel("—");
        setProgress(0);
        return;
      }
      setLabel(clock.label);
      setProgress(clock.progress);
      if (prevCloseMs != null && clock.closeMs !== prevCloseMs) {
        onCandleClose?.();
      }
      prevCloseMs = clock.closeMs;
    };

    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [timeframe, onCandleClose]);

  return (
    <div
      className={
        className ??
        "inline-flex min-w-[7.5rem] flex-col gap-1 rounded-md border border-line/60 bg-panel-elevated/80 px-2.5 py-1.5"
      }
      data-testid="candle-countdown"
      title={`Time left in current ${timeframe} candle`}
    >
      <div className="flex items-center justify-between gap-3 text-[10px] uppercase tracking-[0.14em] text-gold-muted">
        <span>Candle</span>
        <span className="font-mono text-xs tracking-normal text-gold-bright tabular-nums">
          {label}
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-ink/80">
        <div
          className="h-full rounded-full bg-gold/70 transition-[width] duration-1000 ease-linear"
          style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
        />
      </div>
    </div>
  );
}
