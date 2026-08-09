import { useMemo, useState, type ReactNode } from "react";
import {
  runBacktest,
  type BacktestResult,
  type BacktestTradeDto,
} from "../lib/api";
import { formatPrice } from "../lib/chartData";
import { DEFAULT_SYMBOL, TRADE_SYMBOLS, type TradeSymbol } from "../lib/symbols";
import { AiLoader, AiLoaderOverlay } from "./AiLoader";

type Props = {
  onBack: () => void;
};

export function BacktestPage({ onBack }: Props) {
  const [symbol, setSymbol] = useState<TradeSymbol>(DEFAULT_SYMBOL);
  const [timeframe, setTimeframe] = useState("15m");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [equity, setEquity] = useState(100000);
  const [spread, setSpread] = useState(0.3);
  const [slippage, setSlippage] = useState(0.1);
  const [commission, setCommission] = useState(0);
  const [limit, setLimit] = useState(250);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [selected, setSelected] = useState<BacktestTradeDto | null>(null);

  const onRun = async () => {
    setLoading(true);
    setError(null);
    setSelected(null);
    try {
      const data = await runBacktest({
        symbol,
        timeframe,
        start: start || undefined,
        end: end || undefined,
        initial_equity: equity,
        limit,
        warmup_bars: 80,
        cost_config: {
          mode: "REALISTIC_COST",
          spread_points: spread,
          slippage_points: slippage,
          commission_per_trade: commission,
        },
        execution_config: { ambiguity_policy: "CONSERVATIVE", tp_mode: "FULL_AT_TP1" },
      });
      setResult(data);
    } catch (err: unknown) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;

  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="border-b border-line/70 bg-ink-soft/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-3 py-3 sm:px-4 sm:py-4 md:px-6">
          <div className="min-w-0">
            <p className="font-display text-xl font-semibold text-gold-bright sm:text-2xl">
              Backtesting
            </p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-gold-muted sm:text-xs sm:tracking-[0.2em]">
              Phase 7 · Historical measurement only
            </p>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-sm text-cream hover:border-gold/50"
          >
            ← Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1600px] gap-4 px-3 py-4 sm:gap-5 sm:px-4 sm:py-5 md:px-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <section className="min-w-0 space-y-3 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
            Parameters
          </h2>
          <Field label="Symbol">
            <select
              className="input"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value as TradeSymbol)}
            >
              {TRADE_SYMBOLS.map((s) => (
                <option key={s.symbol} value={s.symbol}>
                  {s.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Timeframe">
            <select
              className="input"
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
            >
              <option value="15m">15m</option>
              <option value="30m">30m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </Field>
          <Field label="Start (UTC ISO)">
            <input
              className="input"
              placeholder="optional"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label="End (UTC ISO)">
            <input
              className="input"
              placeholder="optional"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Field label="Initial Equity">
            <input
              className="input"
              type="number"
              value={equity}
              onChange={(e) => setEquity(Number(e.target.value))}
            />
          </Field>
          <Field label="Spread (points)">
            <input
              className="input"
              type="number"
              step="0.01"
              value={spread}
              onChange={(e) => setSpread(Number(e.target.value))}
            />
          </Field>
          <Field label="Slippage (points)">
            <input
              className="input"
              type="number"
              step="0.01"
              value={slippage}
              onChange={(e) => setSlippage(Number(e.target.value))}
            />
          </Field>
          <Field label="Commission">
            <input
              className="input"
              type="number"
              step="0.01"
              value={commission}
              onChange={(e) => setCommission(Number(e.target.value))}
            />
          </Field>
          <Field label="Bar limit">
            <input
              className="input"
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </Field>
          <button
            type="button"
            disabled={loading}
            onClick={onRun}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-gold/50 bg-gold/20 px-4 py-2.5 text-sm font-semibold text-gold-bright hover:bg-gold/30 disabled:opacity-50"
          >
            {loading ? (
              <AiLoader label="Running backtest" size="sm" inline />
            ) : (
              "RUN BACKTEST"
            )}
          </button>
          <p className="text-[11px] text-gold-muted">
            Uses mock/provider history. Full causal strategy per bar — keep limit
            modest. No optimizer / no ML.
          </p>
          {error ? (
            <p className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2 text-sm text-bear">
              {error}
            </p>
          ) : null}
        </section>

        <section className="relative min-w-0 space-y-4">
          <AiLoaderOverlay label="Measuring historical edge…" visible={loading} />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Total Trades" value={fmt(m?.trades_entered)} />
            <Stat
              label="Win Rate"
              value={m ? `${(m.win_rate * 100).toFixed(1)}%` : "—"}
            />
            <Stat label="Profit Factor" value={fmt(m?.profit_factor)} />
            <Stat label="Expectancy (R)" value={fmt(m?.expectancy_r)} />
            <Stat label="Net R" value={fmt(m?.net_profit_r)} />
            <Stat
              label="Max DD %"
              value={m ? `${m.max_drawdown_pct.toFixed(2)}%` : "—"}
            />
            <Stat label="Average R" value={fmt(m?.average_r)} />
            <Stat label="Final Equity" value={fmt(m?.final_equity)} />
          </div>

          <Panel title="Equity Curve">
            {result ? <EquityChart points={result.equity_curve} /> : <Empty />}
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="BUY vs SELL">
              <BreakdownTable rows={result?.breakdowns?.direction ?? []} />
            </Panel>
            <Panel title="Score Buckets">
              <BreakdownTable rows={result?.breakdowns?.score_bucket ?? []} />
            </Panel>
          </div>

          <Panel title="Trade Results">
            {!result?.trades?.length ? (
              <Empty />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/50 text-gold-muted">
                      <th className="py-2 pr-2">Time</th>
                      <th className="py-2 pr-2">Dir</th>
                      <th className="py-2 pr-2">Score</th>
                      <th className="py-2 pr-2">Entry</th>
                      <th className="py-2 pr-2">SL</th>
                      <th className="py-2 pr-2">Exit</th>
                      <th className="py-2 pr-2">R</th>
                      <th className="py-2 pr-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t) => (
                      <tr
                        key={t.trade_id}
                        className={`cursor-pointer border-b border-line/30 hover:bg-panel-elevated ${
                          selected?.trade_id === t.trade_id ? "bg-gold/10" : ""
                        }`}
                        onClick={() => setSelected(t)}
                      >
                        <td className="py-2 pr-2 whitespace-nowrap">
                          {(t.entry_time || t.signal_time).slice(0, 16)}
                        </td>
                        <td
                          className={`py-2 pr-2 font-semibold ${
                            t.direction === "BUY" ? "text-bull" : "text-bear"
                          }`}
                        >
                          {t.direction}
                        </td>
                        <td className="py-2 pr-2">{t.score}</td>
                        <td className="py-2 pr-2">
                          {t.entry_price != null ? formatPrice(t.entry_price) : "—"}
                        </td>
                        <td className="py-2 pr-2">{formatPrice(t.stop_loss)}</td>
                        <td className="py-2 pr-2">
                          {t.exit_price != null ? formatPrice(t.exit_price) : "—"}
                        </td>
                        <td className="py-2 pr-2">
                          {t.net_r != null ? t.net_r.toFixed(2) : "—"}
                        </td>
                        <td className="py-2 pr-2">{t.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {selected ? (
            <Panel title="Selected Trade Levels">
              <div className="grid gap-2 text-sm sm:grid-cols-2">
                <Row label="ENTRY" value={fmtPx(selected.entry_price)} />
                <Row label="SL" value={formatPrice(selected.stop_loss)} />
                <Row
                  label="TP"
                  value={
                    selected.selected_tp != null
                      ? formatPrice(selected.selected_tp)
                      : "—"
                  }
                />
                <Row label="EXIT" value={fmtPx(selected.exit_price)} />
                <Row label="Setup" value={selected.setup_id} />
                <Row label="Strategy" value={selected.strategy_version} />
              </div>
              <p className="mt-3 text-[11px] text-gold-muted">
                Visual markers: ENTRY / SL / TP / EXIT for verification. Full
                chart overlay can use these levels on the live dashboard chart.
              </p>
            </Panel>
          ) : null}
        </section>
      </main>
    </div>
  );
}

function EquityChart({
  points,
}: {
  points: BacktestResult["equity_curve"];
}) {
  const path = useMemo(() => {
    const vals = points.filter((p) => p.bar_index >= 0 || Boolean(p.timestamp));
    if (vals.length < 2) return "";
    const eq = vals.map((p) => p.equity);
    const min = Math.min(...eq);
    const max = Math.max(...eq);
    const span = max - min || 1;
    const w = 600;
    const h = 160;
    return vals
      .map((p, i) => {
        const x = (i / (vals.length - 1)) * w;
        const y = h - ((p.equity - min) / span) * (h - 8) - 4;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [points]);

  if (!path) return <Empty />;
  return (
    <svg viewBox="0 0 600 160" className="h-40 w-full text-gold-bright">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function BreakdownTable({
  rows,
}: {
  rows: Array<{ key: string; trades: number; win_rate: number; net_r: number }>;
}) {
  if (!rows.length) return <Empty />;
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="text-gold-muted">
          <th className="py-1">Key</th>
          <th className="py-1">Trades</th>
          <th className="py-1">Win%</th>
          <th className="py-1">Net R</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key} className="border-t border-line/40">
            <td className="py-1.5">{r.key}</td>
            <td className="py-1.5">{r.trades}</td>
            <td className="py-1.5">{(r.win_rate * 100).toFixed(0)}%</td>
            <td className="py-1.5">{r.net_r.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-xs text-muted">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-line/60 bg-panel-elevated/80 px-2.5 py-2 sm:px-3">
      <p className="truncate text-[10px] uppercase tracking-[0.16em] text-gold-muted">{label}</p>
      <p className="mt-1 break-words font-display text-lg text-cream sm:text-xl">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line/30 py-1">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 break-words text-right text-cream">{value}</span>
    </div>
  );
}

function Empty() {
  return <p className="text-sm text-muted">Run a backtest to populate.</p>;
}

function fmt(v: number | undefined | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function fmtPx(v: number | null | undefined): string {
  return v != null ? formatPrice(v) : "—";
}
