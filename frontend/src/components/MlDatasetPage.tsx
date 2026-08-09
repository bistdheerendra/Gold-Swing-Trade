import { useState, type ReactNode } from "react";
import {
  buildMlDataset,
  type MlDatasetResult,
} from "../lib/api";
import { DEFAULT_SYMBOL, TRADE_SYMBOLS, type TradeSymbol } from "../lib/symbols";
import { AiLoader, AiLoaderOverlay } from "./AiLoader";

type Props = { onBack: () => void };

export function MlDatasetPage({ onBack }: Props) {
  const [symbol, setSymbol] = useState<TradeSymbol>(DEFAULT_SYMBOL);
  const [timeframe, setTimeframe] = useState("15m");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [featureVersion, setFeatureVersion] = useState("1.0.0");
  const [labelVersion, setLabelVersion] = useState("1.0.0");
  const [limit, setLimit] = useState(220);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MlDatasetResult | null>(null);

  const onBuild = async () => {
    const safeLimit = Number.isFinite(limit) ? Math.trunc(limit) : 0;
    if (safeLimit < 120) {
      setError("Bar limit must be at least 120 (warmup + features need enough history).");
      return;
    }
    if (safeLimit > 5000) {
      setError("Bar limit must be at most 5000.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await buildMlDataset({
        symbol,
        timeframe,
        start: start || undefined,
        end: end || undefined,
        feature_version: featureVersion,
        label_version: labelVersion,
        limit: safeLimit,
        warmup_bars: 80,
        row_step: 2,
        include_strategy: false,
      });
      setResult(data);
    } catch (err: unknown) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Build failed");
    } finally {
      setLoading(false);
    }
  };

  const meta = result?.metadata;
  const stats = result?.statistics;
  const split = meta?.split;

  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="border-b border-line/70 bg-ink-soft/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-3 py-3 sm:px-4 sm:py-4 md:px-6">
          <div className="min-w-0">
            <p className="font-display text-xl font-semibold text-gold-bright sm:text-2xl">
              ML Dataset
            </p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-gold-muted sm:text-xs sm:tracking-[0.2em]">
              Phase 8 · Features + labels only · No model training
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
            Dataset Builder
          </h2>
          <label className="block text-xs text-muted">
            Symbol
            <select
              className="input mt-1"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value as TradeSymbol)}
            >
              {TRADE_SYMBOLS.map((s) => (
                <option key={s.symbol} value={s.symbol}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-muted">
            Timeframe
            <select className="input mt-1" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              <option value="15m">15m</option>
              <option value="30m">30m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="block text-xs text-muted">
            Start (UTC)
            <input className="input mt-1" value={start} onChange={(e) => setStart(e.target.value)} placeholder="optional" />
          </label>
          <label className="block text-xs text-muted">
            End (UTC)
            <input className="input mt-1" value={end} onChange={(e) => setEnd(e.target.value)} placeholder="optional" />
          </label>
          <label className="block text-xs text-muted">
            Feature Version
            <input className="input mt-1" value={featureVersion} onChange={(e) => setFeatureVersion(e.target.value)} />
          </label>
          <label className="block text-xs text-muted">
            Label Version
            <input className="input mt-1" value={labelVersion} onChange={(e) => setLabelVersion(e.target.value)} />
          </label>
          <label className="block text-xs text-muted">
            Bar limit (min 120)
            <input
              className="input mt-1"
              type="number"
              min={120}
              max={5000}
              step={1}
              value={Number.isFinite(limit) ? limit : ""}
              onChange={(e) => {
                const raw = e.target.value;
                if (raw === "") {
                  setLimit(Number.NaN);
                  return;
                }
                setLimit(Number(raw));
              }}
              onBlur={() => {
                if (!Number.isFinite(limit) || limit < 120) setLimit(220);
                else if (limit > 5000) setLimit(5000);
                else setLimit(Math.trunc(limit));
              }}
            />
          </label>
          <button
            type="button"
            disabled={loading}
            onClick={onBuild}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-gold/50 bg-gold/20 px-4 py-2.5 text-sm font-semibold text-gold-bright hover:bg-gold/30 disabled:opacity-50"
          >
            {loading ? (
              <AiLoader label="Building dataset" size="sm" inline />
            ) : (
              "BUILD DATASET"
            )}
          </button>
          <p className="text-[11px] text-gold-muted">
            FEATURE = past/present · LABEL = future only. Strategy features off by
            default for faster builds.
          </p>
          {error ? (
            <p className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2 text-sm text-bear">{error}</p>
          ) : null}
        </section>

        <section className="relative min-w-0 space-y-4">
          <AiLoaderOverlay label="Building ML dataset…" visible={loading} />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Rows" value={fmt(meta?.row_count)} />
            <Stat label="Features" value={fmt(stats?.feature_count)} />
            <Stat label="Labels" value={fmt(stats?.label_count)} />
            <Stat label="Missing (avg %)" value={avgMissing(stats?.missing_by_feature)} />
            <Stat label="Train" value={fmt(split?.train)} />
            <Stat label="Validation" value={fmt(split?.validation)} />
            <Stat label="Test" value={fmt(split?.test)} />
            <Stat label="Dataset v" value={meta?.dataset_version ?? "—"} />
          </div>

          <Panel title="Class Distribution">
            {!stats?.class_distribution ? (
              <Empty />
            ) : (
              Object.entries(stats.class_distribution).map(([name, rows]) => (
                <div key={name} className="mb-3">
                  <p className="mb-1 text-xs text-gold-muted">{name}</p>
                  <ul className="text-sm text-cream">
                    {rows.map((r) => (
                      <li key={r.key}>
                        {r.key}: {r.count} ({(r.percentage * 100).toFixed(1)}%)
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </Panel>

          <Panel title="Dataset Preview">
            {!result?.preview_rows?.length ? (
              <Empty />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px] text-left text-xs">
                  <thead>
                    <tr className="border-b border-line/50 text-gold-muted">
                      <th className="py-2 pr-2">Timestamp</th>
                      <th className="py-2 pr-2">RSI</th>
                      <th className="py-2 pr-2">ATR%</th>
                      <th className="py-2 pr-2">EMA Align</th>
                      <th className="py-2 pr-2">4H Bias</th>
                      <th className="py-2 pr-2">1H Bias</th>
                      <th className="py-2 pr-2">15M Bias</th>
                      <th className="py-2 pr-2">State</th>
                      <th className="py-2 pr-2">Score</th>
                      <th className="py-2 pr-2">Label</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.preview_rows.slice(0, 15).map((r) => (
                      <tr key={r.timestamp} className="border-b border-line/30">
                        <td className="py-1.5 pr-2 whitespace-nowrap">{r.timestamp.slice(0, 16)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.rsi)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.atr_pct)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.ema_alignment)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.htf_4h_bias)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.htf_1h_bias)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.entry_15m_bias)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.market_state_code)}</td>
                        <td className="py-1.5 pr-2">{fmtNum(r.features.strategy_score)}</td>
                        <td className="py-1.5 pr-2">{String(r.labels.direction ?? r.labels.strategy_outcome ?? "—")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </section>
      </main>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">{title}</h2>
      {children}
    </section>
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

function Empty() {
  return <p className="text-sm text-muted">Build a dataset to populate.</p>;
}

function fmt(v: number | undefined): string {
  return v == null ? "—" : String(v);
}

function fmtNum(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}

function avgMissing(m: Record<string, number> | undefined): string {
  if (!m || !Object.keys(m).length) return "—";
  const vals = Object.values(m);
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  return `${(avg * 100).toFixed(1)}%`;
}
