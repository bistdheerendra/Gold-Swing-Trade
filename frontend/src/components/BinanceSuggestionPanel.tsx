import { useCallback, useEffect, useState } from "react";
import {
  fetchBinanceSuggestion,
  type BinanceSuggestionResponse,
} from "../lib/api";
import { formatPrice } from "../lib/chartData";
import { formatSuggestTime } from "./SignalCard";

/**
 * Research-only Binance PAXGUSDT ML suggestion + research entry/SL/TP.
 * Must never be presented as Delta PAXGUSD / Phase 12 GO.
 */
export function BinanceSuggestionPanel({
  refreshNonce = 0,
  onLoadingChange,
}: {
  /** Bump from parent Refresh button to re-fetch current suggestion. */
  refreshNonce?: number;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [data, setData] = useState<BinanceSuggestionResponse | null>(null);
  const [suggestedAt, setSuggestedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    onLoadingChange?.(true);
    setError(null);
    try {
      const res = await fetchBinanceSuggestion();
      setData(res);
      setSuggestedAt(new Date().toISOString());
    } catch (err: unknown) {
      setData(null);
      setError(err instanceof Error ? err.message : "Suggestion unavailable");
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  }, [onLoadingChange]);

  useEffect(() => {
    void load();
  }, [load, refreshNonce]);

  const signal = data?.signal ?? data?.suggestion ?? "—";
  const conf =
    data?.confidence != null ? `${(data.confidence * 100).toFixed(1)}%` : "—";
  const tone =
    signal === "BUY" || signal === "LEAN_LONG"
      ? "bull"
      : signal === "SHORT" || signal === "SELL" || signal === "LEAN_SHORT"
        ? "bear"
        : "wait";
  const toneBox =
    tone === "bull"
      ? "border-binance-green/50 bg-binance-green/10"
      : tone === "bear"
        ? "border-binance-red/50 bg-binance-red/10"
        : "border-binance/35 bg-white/5";
  const signalColor =
    tone === "bull"
      ? "text-binance-green"
      : tone === "bear"
        ? "text-binance-red"
        : "text-white";

  const entryLabel =
    data?.entry != null
      ? `${formatPrice(data.entry.low)} – ${formatPrice(data.entry.high)}`
      : "—";
  const tp1 = data?.targets?.[0];
  const tp2 = data?.targets?.[1];
  const showLevels = signal === "BUY" || signal === "SHORT";
  const suggestStamp =
    suggestedAt || data?.generated_at || data?.as_of || null;

  return (
    <div
      data-testid="binance-suggestion-panel"
      className="space-y-3 text-white"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-binance px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-binance-ink">
          Binance
        </span>
        <span className="text-[10px] uppercase tracking-wider text-white/55">
          Futures · PAXGUSDT · research only
        </span>
      </div>

      <p className="text-[11px] leading-relaxed text-white/55">
        Binance-trained reference. Separate from Delta PAXGUSD strategy — not
        Phase 12 GO. Levels use Binance SMC/ATR geometry for the ML lean.
      </p>

      {loading && !data ? (
        <p className="text-sm text-white/60">Loading Binance suggestion…</p>
      ) : error ? (
        <p className="rounded-lg border border-binance-red/40 bg-binance-red/10 px-3 py-2 text-sm text-binance-red">
          {error}
        </p>
      ) : data && data.enabled === false ? (
        <p className="text-sm text-white/60">{data.error ?? "Disabled"}</p>
      ) : data ? (
        <>
          <div
            className={`relative rounded-xl border px-3 py-2.5 text-center ${toneBox}`}
          >
            <span
              className="absolute right-2 top-2 rounded-md border border-binance/40 bg-binance-ink/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-binance"
              title={
                data.train_from && data.train_to
                  ? `${data.train_from.slice(0, 10)} → ${data.train_to.slice(0, 10)}`
                  : "Binance training window"
              }
              data-testid="binance-train-span-badge"
            >
              {data.train_span_label ?? "16.5 mo train"}
            </span>
            <p className="text-[10px] uppercase tracking-wider text-white/55">
              {data.symbol ?? "PAXGUSDT"} · model lean
            </p>
            <p className={`mt-1 font-display text-2xl font-semibold ${signalColor}`}>
              {signal}
            </p>
            <p className="mt-1 text-xs text-white/80">
              Confidence {conf}
              {data.suggestion && data.suggestion !== signal
                ? ` · ${data.suggestion}`
                : ""}
            </p>
            {suggestStamp ? (
              <p
                className="mt-2 text-[11px] text-white/70"
                data-testid="binance-suggested-at"
                title={data.as_of ? `Bar as of ${data.as_of}` : undefined}
              >
                Suggested · {formatSuggestTime(suggestStamp)}
                {loading ? " · updating…" : ""}
              </p>
            ) : null}
          </div>

          {showLevels ? (
            <div className="space-y-1.5 text-sm">
              <Row label="Entry" value={entryLabel} valueTone="entry" />
              <Row
                label="Preferred"
                value={
                  data.entry?.preferred != null
                    ? formatPrice(data.entry.preferred)
                    : "—"
                }
                valueTone="entry"
              />
              <Row
                label="Spot"
                value={
                  data.bar_close != null ? formatPrice(data.bar_close) : "—"
                }
                valueTone="spot"
              />
              <Row
                label="SL"
                value={
                  data.stop_loss != null ? formatPrice(data.stop_loss) : "—"
                }
                valueTone="sl"
              />
              <Row
                label="TP1"
                value={
                  tp1
                    ? `${formatPrice(tp1.price)} · RR 1:${Number(tp1.rr).toFixed(2)}`
                    : "—"
                }
                valueTone="tp"
              />
              <Row
                label="TP2"
                value={
                  tp2
                    ? `${formatPrice(tp2.price)} · RR 1:${Number(tp2.rr).toFixed(2)}`
                    : "—"
                }
                valueTone="tp"
              />
              <Row
                label="Primary RR"
                value={
                  data.primary_rr != null
                    ? `1:${Number(data.primary_rr).toFixed(2)}`
                    : "—"
                }
                valueTone="tp"
              />
              {suggestStamp ? (
                <Row
                  label="Suggested at"
                  value={formatSuggestTime(suggestStamp)}
                />
              ) : null}
              {(data.level_errors?.length ?? 0) > 0 ? (
                <p className="pt-1 text-[11px] text-binance-red">
                  {data.level_errors?.[0]}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-1.5 text-sm">
              <p className="text-[11px] text-white/55">
                No near-spot trade levels — entry/SL/TP shown when Binance lean
                has an actionable setup.
              </p>
              {suggestStamp ? (
                <Row
                  label="Suggested at"
                  value={formatSuggestTime(suggestStamp)}
                />
              ) : null}
              {(data.level_errors?.length ?? 0) > 0 ? (
                <p className="pt-1 text-[11px] text-binance-red">
                  {data.level_errors?.[0]}
                </p>
              ) : null}
            </div>
          )}

          <dl className="grid grid-cols-2 gap-2 text-[11px] text-white/50">
            <div>
              <dt className="uppercase tracking-wider">Model</dt>
              <dd className="truncate font-medium text-white" title={data.model_id}>
                {data.model_id ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wider">Market as of</dt>
              <dd className="truncate font-medium text-white">
                {data.as_of ? formatSuggestTime(data.as_of) : "—"}
              </dd>
            </div>
          </dl>
        </>
      ) : null}
    </div>
  );
}

function Row({
  label,
  value,
  valueTone,
}: {
  label: string;
  value: string;
  valueTone?: "entry" | "spot" | "sl" | "tp";
}) {
  const valueClass =
    valueTone === "sl"
      ? "text-binance-red"
      : valueTone === "tp"
        ? "text-binance-green"
        : "text-white";
  const labelClass =
    valueTone === "sl"
      ? "text-binance-red/75"
      : valueTone === "tp"
        ? "text-binance-green/75"
        : "text-white/55";

  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className={`shrink-0 ${labelClass}`}>{label}</span>
      <span className={`min-w-0 break-words text-right font-semibold ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}
