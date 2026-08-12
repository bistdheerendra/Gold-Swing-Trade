import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ChevronDown } from "lucide-react";
import type { EmaPeriod } from "../../lib/ema";
import { DEFAULT_EMA_PERIODS } from "../../lib/ema";
import { EMA_COLORS } from "../../lib/chartData";
import type { SmcOverlayKey, SmcOverlayVisibility } from "../../lib/smcTheme";

const SMC_ITEMS: { id: SmcOverlayKey; label: string }[] = [
  { id: "swing", label: "Swing High/Low" },
  { id: "bos", label: "BOS" },
  { id: "choch", label: "CHoCH" },
  { id: "fvg", label: "FVG" },
  { id: "ob", label: "Order Block" },
  { id: "zones", label: "Demand/Supply" },
  { id: "liq", label: "Liquidity" },
  { id: "sweep", label: "Liquidity Sweep" },
];

type ChartOverlayMenusProps = {
  emaVisibility: Record<EmaPeriod, boolean>;
  onEmaChange: (period: EmaPeriod, visible: boolean) => void;
  smcVisibility: SmcOverlayVisibility;
  onSmcToggle: (id: SmcOverlayKey) => void;
};

export function ChartOverlayMenus({
  emaVisibility,
  onEmaChange,
  smcVisibility,
  onSmcToggle,
}: ChartOverlayMenusProps) {
  const emaActive = DEFAULT_EMA_PERIODS.filter((p) => emaVisibility[p]).length;
  const smcActive = SMC_ITEMS.filter((i) => smcVisibility[i.id]).length;

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <OverlayDropdown
        label="EMA"
        testId="ema-overlays-menu"
        summary={emaActive > 0 ? String(emaActive) : undefined}
        active={emaActive > 0}
      >
        <p className="mb-1.5 px-1 text-[10px] uppercase tracking-wider text-gold-muted">
          EMA overlays
        </p>
        <div className="flex flex-col gap-0.5">
          {DEFAULT_EMA_PERIODS.map((period) => {
            const on = emaVisibility[period];
            return (
              <button
                key={period}
                type="button"
                onClick={() => onEmaChange(period, !on)}
                className={`flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-left text-[12px] transition ${
                  on
                    ? "bg-panel-elevated text-cream"
                    : "text-muted hover:bg-panel-elevated/60"
                }`}
              >
                <span>EMA {period}</span>
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background: on ? EMA_COLORS[period] : "transparent",
                    boxShadow: on
                      ? `0 0 0 1px ${EMA_COLORS[period]}`
                      : "0 0 0 1px var(--color-line)",
                  }}
                />
              </button>
            );
          })}
        </div>
      </OverlayDropdown>

      <OverlayDropdown
        label="SMC"
        testId="smc-overlays-menu"
        summary={smcActive > 0 ? String(smcActive) : undefined}
        active={smcActive > 0}
      >
        <p className="mb-1.5 px-1 text-[10px] uppercase tracking-wider text-gold-muted">
          SMC overlays
        </p>
        <p className="mb-2 px-1 text-[10px] leading-snug text-muted">
          Confirmed events only · no look-ahead
        </p>
        <div className="flex max-h-64 flex-col gap-0.5 overflow-y-auto">
          {SMC_ITEMS.map((item) => {
            const on = Boolean(smcVisibility[item.id]);
            return (
              <label
                key={item.id}
                className="flex cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-1.5 text-[12px] text-cream/90 hover:bg-panel-elevated"
              >
                <span className="truncate">{item.label}</span>
                <input
                  type="checkbox"
                  className="accent-gold"
                  checked={on}
                  onChange={() => onSmcToggle(item.id)}
                />
              </label>
            );
          })}
        </div>
      </OverlayDropdown>
    </div>
  );
}

function OverlayDropdown({
  label,
  summary,
  active,
  testId,
  children,
}: {
  label: string;
  summary?: string;
  active?: boolean;
  testId: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={rootRef} data-testid={testId}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[11px] uppercase tracking-wide transition ${
          open || active
            ? "border-gold/50 bg-gold/15 text-gold"
            : "border-line/70 text-muted opacity-70 hover:border-line hover:opacity-100"
        }`}
      >
        {label}
        {summary ? (
          <span className="rounded bg-ink/50 px-1 text-[10px] normal-case tracking-normal text-gold-bright">
            {summary}
          </span>
        ) : null}
        <ChevronDown
          className={`h-3 w-3 transition ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-40 mt-1.5 w-52 rounded-xl border border-line/70 bg-panel-elevated p-2 shadow-lg shadow-black/40"
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
