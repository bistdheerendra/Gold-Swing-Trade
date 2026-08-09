import type { EmaPeriod } from "../../lib/ema";
import { DEFAULT_EMA_PERIODS } from "../../lib/ema";
import { EMA_COLORS } from "../../lib/chartData";

type EmaToggleBarProps = {
  visibility: Record<EmaPeriod, boolean>;
  onChange: (period: EmaPeriod, visible: boolean) => void;
};

export function EmaToggleBar({ visibility, onChange }: EmaToggleBarProps) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="EMA overlays">
      {DEFAULT_EMA_PERIODS.map((period) => {
        const active = visibility[period];
        return (
          <button
            key={period}
            type="button"
            onClick={() => onChange(period, !active)}
            className={`rounded-md border px-2 py-1 text-[11px] uppercase tracking-wide transition ${
              active
                ? "border-transparent bg-panel-elevated text-cream"
                : "border-line/70 text-muted opacity-60"
            }`}
            style={active ? { boxShadow: `inset 0 -2px 0 ${EMA_COLORS[period]}` } : undefined}
          >
            EMA {period}
          </button>
        );
      })}
    </div>
  );
}
