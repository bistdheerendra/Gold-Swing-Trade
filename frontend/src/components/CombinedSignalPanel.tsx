import { useState } from "react";
import {
  compareRuleVsMl,
  fetchCombinedAnalyze,
  type CombinedSignalResponse,
  type CombinedCompareResult,
} from "../lib/api";
import { formatPrice } from "../lib/chartData";
import { AiLoader } from "./AiLoader";

function tone(signal: string): string {
  if (signal === "BUY") return "text-bull border-bull/40 bg-bull/10";
  if (signal === "SELL") return "text-bear border-bear/40 bg-bear/10";
  return "text-wait border-wait/30 bg-wait/10";
}

export function CombinedSignalPanel({
  modelId,
  symbol,
}: {
  modelId?: string;
  symbol?: string;
}) {
  const [data, setData] = useState<CombinedSignalResponse | null>(null);
  const [compare, setCompare] = useState<CombinedCompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCombinedAnalyze({
        model_id: modelId,
        mode: "ML_FILTER",
        symbol,
      });
      setData(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  const runCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await compareRuleVsMl({
        model_id: modelId,
        symbol,
        min_ml_confidence: 0.6,
        run_threshold_scan: false,
        evaluate_test: true,
        // TEST is ~15% of the window; need enough bars to clear validation mins.
        limit: 400,
      });
      setCompare(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Compare failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="combined-signal-panel">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex min-h-[2rem] min-w-0 flex-1 items-center justify-center rounded-lg border border-gold/40 px-3 py-1.5 text-xs text-gold-bright hover:bg-gold/10 disabled:opacity-50 sm:min-w-[8.5rem] sm:flex-none"
        >
          {loading ? <AiLoader label="" size="sm" inline /> : "Analyze combined"}
        </button>
        <button
          type="button"
          onClick={runCompare}
          disabled={loading}
          className="flex min-h-[2rem] min-w-0 flex-1 items-center justify-center rounded-lg border border-line px-3 py-1.5 text-xs text-cream hover:border-gold/40 disabled:opacity-50 sm:flex-none"
        >
          {loading ? <AiLoader label="" size="sm" inline /> : "Rule vs ML (TEST)"}
        </button>
      </div>
      {loading ? (
        <div className="rounded-xl border border-line/50 bg-ink/40 py-6">
          <AiLoader label="AI signal analysis" size="md" />
        </div>
      ) : null}
      <p className="text-[10px] uppercase tracking-wider text-gold-muted">
        RESEARCH ONLY · not profit probability
      </p>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {data ? (
        <div className="space-y-3">
          <div className={`rounded-xl border p-4 text-center ${tone(data.direction)}`}>
            <p className="text-xs uppercase tracking-[0.2em] text-gold-muted">Final</p>
            <p className="mt-1 break-words font-display text-2xl sm:text-3xl">{data.direction}</p>
            <p className="mt-2 text-xs text-muted">{data.ml_status}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Stat label="Rule signal" value={data.rule_signal} />
            <Stat label="Rule score" value={`${data.rule_score}/100`} />
            <Stat label="ML prediction" value={data.ml_prediction ?? "—"} />
            <Stat
              label="ML confidence"
              value={
                data.ml_confidence != null
                  ? `${(data.ml_confidence * 100).toFixed(0)}%`
                  : "—"
              }
            />
          </div>
          {!data.probability_calibrated ? (
            <p className="text-[11px] text-muted">
              probability_calibrated=false — do not treat as win odds
            </p>
          ) : null}
          <Row
            label="Entry"
            value={
              data.entry
                ? `${formatPrice(data.entry.low)} – ${formatPrice(data.entry.high)}`
                : "—"
            }
          />
          <Row
            label="SL"
            value={data.stop_loss != null ? formatPrice(data.stop_loss) : "—"}
          />
          <Row
            label="TP1"
            value={
              data.targets[0]
                ? `${formatPrice(data.targets[0].price)} · RR ${data.targets[0].rr}`
                : "—"
            }
          />
          <Block title="Rule reasons" items={data.rule_reasons} />
          <Block title="ML reasons" items={data.ml_reasons} />
          <Block title="Risks" items={data.risks} />
        </div>
      ) : (
        <p className="text-sm text-muted">Run analyze to load Rule + ML signal.</p>
      )}

      {compare ? (
        <div className="rounded-xl border border-line/60 p-3 text-sm overflow-x-auto">
          <p className="mb-2 text-xs uppercase tracking-wider text-gold-muted">
            RULE ONLY vs RULE + ML · {compare.split}
          </p>
          <p className="mb-2 text-[11px] text-muted">
            threshold {compare.threshold_frozen_from_validation} (validation-frozen)
          </p>
          <table className="w-full min-w-[240px] text-left text-xs text-cream">
            <thead>
              <tr className="text-muted">
                <th className="py-1">Metric</th>
                <th>RULE</th>
                <th>ML filter</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ["trades", "trades"],
                  ["win_rate", "win_rate"],
                  ["profit_factor", "profit_factor"],
                  ["expectancy_r", "expectancy_r"],
                  ["net_r", "net_r"],
                  ["max_drawdown_pct", "max_drawdown_pct"],
                ] as const
              ).map(([label, key]) => (
                <tr key={key}>
                  <td className="py-0.5 text-muted">{label}</td>
                  <td>{String(compare.RULE_ONLY[key] ?? "—")}</td>
                  <td>{String(compare.ML_FILTER[key] ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">
            Filtered {compare.filter_quality.trades_filtered} · losers avoided{" "}
            {compare.filter_quality.losers_avoided} · winners rejected{" "}
            {compare.filter_quality.winners_rejected}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line/40 p-2">
      <p className="text-[10px] uppercase text-gold-muted">{label}</p>
      <p className="text-cream">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-cream">{value}</span>
    </div>
  );
}

function Block({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="mb-1 text-[10px] uppercase tracking-wider text-gold-muted">{title}</p>
      <ul className="space-y-1 text-xs text-muted">
        {items.slice(0, 6).map((r) => (
          <li key={r}>• {r}</li>
        ))}
      </ul>
    </div>
  );
}
