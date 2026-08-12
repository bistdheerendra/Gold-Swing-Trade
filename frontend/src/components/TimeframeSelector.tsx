import type { Timeframe } from "../lib/api";
import { TIMEFRAMES } from "../lib/api";

type TimeframeSelectorProps = {
  value: Timeframe;
  onChange: (timeframe: Timeframe) => void;
  disabled?: boolean;
};

export function TimeframeSelector({
  value,
  onChange,
  disabled = false,
}: TimeframeSelectorProps) {
  return (
    <div
      className="flex gap-1.5 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      role="tablist"
      aria-label="Chart timeframe"
    >
      {TIMEFRAMES.map((tf) => {
        const active = tf === value;
        return (
          <button
            key={tf}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            onClick={() => onChange(tf)}
            className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs uppercase tracking-wide transition sm:px-3 ${
              active
                ? "bg-gold/20 text-gold-bright ring-1 ring-gold/40"
                : "text-muted hover:bg-panel-elevated hover:text-cream"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
}
