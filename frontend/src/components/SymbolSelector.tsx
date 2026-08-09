import { TRADE_SYMBOLS, type TradeSymbol } from "../lib/symbols";

type Props = {
  value: TradeSymbol;
  onChange: (symbol: TradeSymbol) => void;
};

export function SymbolSelector({ value, onChange }: Props) {
  return (
    <div
      className="inline-flex max-w-full flex-wrap rounded-full border border-line/80 bg-ink/40 p-0.5"
      role="tablist"
      aria-label="Symbol"
    >
      {TRADE_SYMBOLS.map((s) => {
        const active = s.symbol === value;
        return (
          <button
            key={s.symbol}
            type="button"
            role="tab"
            aria-selected={active}
            title={s.description}
            onClick={() => onChange(s.symbol)}
            className={
              active
                ? "rounded-full bg-gold/20 px-2.5 py-1 text-xs font-semibold text-gold-bright sm:px-3"
                : "rounded-full px-2.5 py-1 text-xs text-muted hover:text-cream sm:px-3"
            }
          >
            {s.shortLabel}
          </button>
        );
      })}
    </div>
  );
}
