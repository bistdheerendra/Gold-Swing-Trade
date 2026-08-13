import { useState, type ReactNode } from "react";
import {
  buildMlDataset,
  listMlModels,
  trainMlModel,
  type MlDatasetResult,
  type MlModelSummary,
  type MlTrainResult,
} from "../lib/api";
import { DEFAULT_SYMBOL, TRADE_SYMBOLS, type TradeSymbol } from "../lib/symbols";
import { AiLoader, AiLoaderOverlay } from "./AiLoader";

const TARGETS = [
  "direction",
  "strategy_outcome",
  "multiclass_outcome",
  "return_10",
  "future_R",
] as const;

const MODEL_TYPES = ["logistic", "random_forest", "gradient_boosting", ""] as const;

export function MlModelLabPage() {
  const [symbol, setSymbol] = useState<TradeSymbol>(DEFAULT_SYMBOL);
  const [datasetId, setDatasetId] = useState("");
  const [dataset, setDataset] = useState<MlDatasetResult | null>(null);
  const [target, setTarget] = useState<string>("direction");
  const [modelType, setModelType] = useState<string>("");
  const [seed, setSeed] = useState(42);
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MlTrainResult | null>(null);
  const [models, setModels] = useState<MlModelSummary[]>([]);

  const refreshModels = async () => {
    try {
      const data = await listMlModels();
      setModels(data.models);
    } catch {
      /* ignore */
    }
  };

  const onBuildDataset = async () => {
    setBuilding(true);
    setError(null);
    try {
      const data = await buildMlDataset({
        symbol,
        timeframe: "15m",
        limit: 240,
        warmup_bars: 80,
        row_step: 2,
        include_strategy: true,
      });
      setDataset(data);
      setDatasetId(data.dataset_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Dataset build failed");
    } finally {
      setBuilding(false);
    }
  };

  const onTrain = async () => {
    if (!datasetId.trim()) {
      setError("Provide a dataset_id (build one first)");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await trainMlModel({
        dataset_id: datasetId.trim(),
        target,
        model_type: modelType || undefined,
        random_seed: seed,
        run_test: true,
      });
      setResult(data);
      await refreshModels();
    } catch (err: unknown) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Training failed");
    } finally {
      setLoading(false);
    }
  };

  const trainM = result?.train_metrics;
  const valM = result?.validation_metrics;
  const testM = result?.test_metrics;
  const filter = result?.test_filter;

  return (
    <div className="overflow-x-hidden">
      <div className="mx-auto max-w-[1600px] px-3 pt-4 sm:px-4 md:px-6">
        <h1 className="font-display text-xl font-semibold text-gold-bright sm:text-2xl">
          ML Model Lab
        </h1>
        <p className="text-[10px] uppercase tracking-[0.18em] text-gold-muted sm:text-xs sm:tracking-[0.2em]">
          Phase 9 · RESEARCH ONLY · No live predictions
        </p>
      </div>

      <main className="mx-auto grid max-w-[1600px] gap-4 px-3 py-4 sm:gap-5 sm:px-4 sm:py-5 md:px-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <section className="min-w-0 space-y-3 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
            Train (research)
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
          <button
            type="button"
            onClick={onBuildDataset}
            disabled={building}
            className="w-full rounded-lg border border-gold/40 bg-gold/10 px-3 py-2 text-sm text-gold-bright hover:bg-gold/20 disabled:opacity-50"
          >
            {building ? "Building dataset…" : "Build Phase 8 dataset"}
          </button>
          {dataset ? (
            <p className="text-xs text-muted">
              Rows {dataset.metadata.row_count} · Features {dataset.metadata.feature_count}
            </p>
          ) : null}
          <label className="block text-xs text-muted">
            Dataset ID
            <input
              className="input mt-1"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
            />
          </label>
          <label className="block text-xs text-muted">
            Target
            <select
              className="input mt-1"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              {TARGETS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-muted">
            Model (blank = compare all on validation)
            <select
              className="input mt-1"
              value={modelType}
              onChange={(e) => setModelType(e.target.value)}
            >
              <option value="">all (select on validation)</option>
              {MODEL_TYPES.filter(Boolean).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-muted">
            Random seed
            <input
              className="input mt-1"
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            onClick={onTrain}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-medium text-ink hover:bg-gold-bright disabled:opacity-50"
          >
            {loading ? (
              <AiLoader label="Training model" size="sm" inline />
            ) : (
              "Train"
            )}
          </button>
          {error ? <p className="text-sm text-rose-300">{error}</p> : null}
        </section>

        <section className="relative min-w-0 space-y-4">
          <AiLoaderOverlay label="Training AI model…" visible={loading} />
          {!result ? (
            <p className="rounded-2xl border border-dashed border-line/60 p-4 text-center text-sm text-muted sm:p-8">
              Build a dataset, choose a target, then train. Metrics are research-only.
              Model selection uses VALIDATION; TEST is held out until after selection.
            </p>
          ) : (
            <>
              <Banner
                title={`${result.selected_model_type} · ${result.target}`}
                subtitle={`model_id ${result.model_id} · status ${result.status}${
                  result.overfitting ? ` · ${result.overfitting}` : ""
                }`}
              />
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
                <MetricCard title="Train" metrics={trainM} />
                <MetricCard title="Validation" metrics={valM} />
                <MetricCard title="Test (held-out)" metrics={testM} />
              </div>

              {result.feature_importance?.length ? (
                <Panel title="Feature importance (descriptive)">
                  <ul className="space-y-1 text-sm text-cream">
                    {result.feature_importance.slice(0, 12).map((f) => (
                      <li key={f.feature} className="flex justify-between gap-4">
                        <span className="truncate text-muted">{f.feature}</span>
                        <span>{f.importance}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              ) : null}

              {trainM && "confusion_matrix" in trainM ? (
                <Panel title="Confusion matrix (train)">
                  <ConfusionMatrix cm={(trainM as { confusion_matrix: Record<string, Record<string, number>> }).confusion_matrix} />
                </Panel>
              ) : null}

              {filter && !("error" in filter) ? (
                <Panel title="Rule vs Rule+ML filter (TEST · threshold from validation)">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <TradingBlock label="Phase 6 rule only" m={filter.rule_only} />
                    <TradingBlock label="Rule + ML filter" m={filter.rule_plus_ml} />
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    Threshold {filter.threshold} · tags{" "}
                    {JSON.stringify(filter.tag_counts)}
                  </p>
                </Panel>
              ) : null}

              {result.baselines ? (
                <Panel title="Baselines (validation)">
                  <pre className="overflow-auto text-xs text-muted">
                    {JSON.stringify(result.baselines, null, 2)}
                  </pre>
                </Panel>
              ) : null}
            </>
          )}

          {models.length > 0 ? (
            <Panel title="Registry (RESEARCH)">
              <ul className="space-y-1 text-sm">
                {models.map((m) => (
                  <li key={m.model_id} className="text-muted">
                    <span className="text-cream">{m.model_id}</span> · {m.target} ·{" "}
                    {m.model_type}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </section>
      </main>
    </div>
  );
}

function Banner({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="rounded-2xl border border-gold/30 bg-gold/5 px-3 py-3 sm:px-4">
      <p className="break-words font-display text-base text-gold-bright sm:text-lg">{title}</p>
      <p className="break-all text-xs text-muted">{subtitle}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
        {title}
      </h3>
      {children}
    </div>
  );
}

function MetricCard({
  title,
  metrics,
}: {
  title: string;
  metrics?: Record<string, unknown> | null;
}) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="rounded-2xl border border-line/50 bg-panel/50 p-3 text-sm text-muted">
        <p className="mb-1 text-xs uppercase text-gold-muted">{title}</p>
        —
      </div>
    );
  }
  const keys = ["f1_macro", "accuracy", "balanced_accuracy", "mae", "rmse", "r2", "directional_accuracy"];
  return (
    <div className="rounded-2xl border border-line/70 bg-panel/80 p-3">
      <p className="mb-2 text-xs uppercase tracking-wider text-gold-muted">{title}</p>
      <ul className="space-y-1 text-sm text-cream">
        {keys
          .filter((k) => metrics[k] != null)
          .map((k) => (
            <li key={k} className="flex justify-between gap-2">
              <span className="text-muted">{k}</span>
              <span>{String(metrics[k])}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}

function ConfusionMatrix({
  cm,
}: {
  cm: Record<string, Record<string, number>>;
}) {
  const labels = Object.keys(cm);
  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-xs text-cream">
        <thead>
          <tr>
            <th className="p-1 text-muted">actual\\pred</th>
            {labels.map((l) => (
              <th key={l} className="p-1 text-muted">
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((a) => (
            <tr key={a}>
              <td className="p-1 text-muted">{a}</td>
              {labels.map((b) => (
                <td key={b} className="p-1">
                  {cm[a]?.[b] ?? 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradingBlock({
  label,
  m,
}: {
  label: string;
  m?: {
    trades?: number;
    win_rate?: number;
    profit_factor?: number;
    expectancy_r?: number;
    net_r?: number;
    max_drawdown_r?: number;
  };
}) {
  if (!m) return null;
  return (
    <div className="rounded-lg border border-line/40 p-3 text-sm">
      <p className="mb-2 text-xs uppercase text-gold-muted">{label}</p>
      <ul className="space-y-1 text-cream">
        <li>trades {m.trades}</li>
        <li>win rate {m.win_rate}</li>
        <li>PF {m.profit_factor}</li>
        <li>expectancy R {m.expectancy_r}</li>
        <li>net R {m.net_r}</li>
        <li>max DD R {m.max_drawdown_r}</li>
      </ul>
    </div>
  );
}
