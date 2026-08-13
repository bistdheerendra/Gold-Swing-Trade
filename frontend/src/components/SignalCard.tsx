import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { StrategyAnalyzeResponse, StrategySignalDto } from "../lib/api";
import { formatPrice } from "../lib/chartData";
import { AiLoader } from "./AiLoader";

function signalTone(signal: string): "bull" | "bear" | "wait" {
  if (signal === "BUY") return "bull";
  if (signal === "SELL") return "bear";
  return "wait";
}

function signalEmoji(signal: string): string {
  if (signal === "BUY") return "BUY";
  if (signal === "SELL") return "SELL";
  if (signal === "NO_TRADE") return "NO TRADE";
  return "WAIT";
}

export function SignalCard({
  data,
  symbolLabel,
  lastClose,
  suggestedAt,
  refreshing = false,
}: {
  data: StrategyAnalyzeResponse | null;
  symbolLabel?: string;
  /** Latest chart/spot close — used to flag pullback vs market entry. */
  lastClose?: number | null;
  /** Client clock when this suggestion was fetched / refreshed. */
  suggestedAt?: string | null;
  refreshing?: boolean;
}) {
  const [reasonsOpen, setReasonsOpen] = useState(false);

  if (!data) {
    return <AiLoader label="Loading strategy signal" size="sm" />;
  }

  const tone = signalTone(data.signal);
  const toneBorder =
    tone === "bull"
      ? "border-bull/40 bg-bull/10"
      : tone === "bear"
        ? "border-bear/40 bg-bear/10"
        : "border-wait/30 bg-wait/10";
  const toneText =
    tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "text-wait";

  const entryLabel =
    data.entry != null
      ? `${formatPrice(data.entry.low)} – ${formatPrice(data.entry.high)}`
      : "—";
  const tp1 = data.targets[0];
  const tp2 = data.targets[1];
  const title = symbolLabel ?? data.symbol ?? "PAXGUSD";
  const levelsAreCandidates =
    data.signal === "NO_TRADE" || data.signal === "WAIT";
  const hasAnyLevel =
    data.entry != null ||
    data.stop_loss != null ||
    (data.targets?.length ?? 0) > 0;

  const spot =
    lastClose != null && Number.isFinite(lastClose) ? lastClose : null;
  const entryAway = entryDistanceNote(data.signal, data.entry ?? null, spot);
  const suggestStamp = suggestedAt || data.as_of;
  const reasonItems = data.reasons.length ? data.reasons : ["—"];

  return (
    <div className="space-y-4">
      <div className={`rounded-xl border p-4 text-center ${toneBorder}`}>
        <p className="text-xs uppercase tracking-[0.2em] text-gold-muted">
          {title}
        </p>
        <p className={`mt-2 font-display text-3xl sm:text-4xl ${toneText}`}>
          {signalEmoji(data.signal)}
        </p>
        <p className="mt-2 text-sm text-cream">
          Strategy Score:{" "}
          <span className="text-gold-bright">{data.score}</span>
          <span className="text-muted"> / 100</span>
        </p>
        <p className="mt-1 text-[11px] text-gold-muted">{data.score_label}</p>
        {suggestStamp ? (
          <p
            className="mt-2 text-[11px] text-cream/85"
            data-testid="signal-suggested-at"
            title={data.as_of ? `Market as of ${data.as_of}` : undefined}
          >
            Suggested · {formatSuggestTime(suggestStamp)}
            {refreshing ? " · updating…" : ""}
          </p>
        ) : null}
        {data.signal === "WAIT" && data.reasons[0] ? (
          <p className="mt-3 text-sm text-muted">{data.reasons[0]}</p>
        ) : null}
        {data.signal === "NO_TRADE" && data.reasons[0] ? (
          <p className="mt-3 text-sm text-muted">{data.reasons[0]}</p>
        ) : null}
      </div>

      {entryAway ? (
        <div
          className="rounded-lg border border-wait/40 bg-wait/10 px-3 py-2 text-left text-[12px] leading-relaxed text-cream/90"
          data-testid="entry-pullback-note"
        >
          <p className="font-medium text-wait">{entryAway.title}</p>
          <p className="mt-1 text-muted">{entryAway.detail}</p>
        </div>
      ) : null}

      <div className="space-y-2 text-sm">
        {levelsAreCandidates && hasAnyLevel ? (
          <p className="text-[10px] uppercase tracking-wider text-gold-muted">
            Candidate levels · not an active trade
          </p>
        ) : null}
        {levelsAreCandidates && !hasAnyLevel ? (
          <p className="text-[11px] text-muted">
            No entry/SL/TP yet — levels need a valid zone + RR. Unmet conditions
            (e.g. liquidity sweep) often block a complete plan.
          </p>
        ) : null}
        <Row label="Entry" value={entryLabel} />
        {spot != null ? (
          <Row label="Spot (last)" value={formatPrice(spot)} />
        ) : null}
        <Row
          label="SL"
          value={data.stop_loss != null ? formatPrice(data.stop_loss) : "—"}
        />
        <Row
          label="TP1"
          value={
            tp1
              ? `${formatPrice(tp1.price)} · RR 1:${tp1.rr.toFixed(2)}`
              : "—"
          }
        />
        <Row
          label="TP2"
          value={
            tp2
              ? `${formatPrice(tp2.price)} · RR 1:${tp2.rr.toFixed(2)}`
              : "—"
          }
        />
        <Row
          label="Primary RR"
          value={
            data.primary_rr != null ? `1:${data.primary_rr.toFixed(2)}` : "—"
          }
        />
        {entryAway ? (
          <p className="text-[10px] text-gold-muted">
            RR is measured from preferred entry inside the zone — not from spot.
          </p>
        ) : null}
      </div>

      <div className="space-y-1 border-t border-line/40 pt-3 text-sm">
        <Row label="Status" value={data.status} />
        {suggestStamp ? (
          <Row label="Suggested at" value={formatSuggestTime(suggestStamp)} />
        ) : null}
      </div>

      <div>
        <button
          type="button"
          onClick={() => setReasonsOpen((open) => !open)}
          aria-expanded={reasonsOpen}
          className="flex w-full items-center justify-between gap-2 text-left"
          data-testid="signal-reasons-toggle"
        >
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
            Reasons
            <span className="ml-2 normal-case tracking-normal text-muted">
              ({reasonItems.length})
            </span>
          </span>
          <ChevronDown
            className={`h-3.5 w-3.5 shrink-0 text-gold-muted transition ${
              reasonsOpen ? "rotate-180" : ""
            }`}
          />
        </button>
        {reasonsOpen ? (
          <ul className="mt-2 space-y-1.5 text-sm text-cream/90">
            {reasonItems.map((r) => (
              <li key={r} className="leading-snug">
                {r}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
          Risks
        </p>
        <ul className="space-y-1.5 text-sm text-muted">
          {(data.risks.length ? data.risks : ["No flagged risks"]).map((r) => (
            <li key={r} className="leading-snug">
              {r}
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[11px] text-gold-muted">
        strategy v{data.strategy_version} · score is condition weight, not win
        probability
      </p>
    </div>
  );
}

export function SignalHistoryTable({
  signals,
}: {
  signals: StrategySignalDto[];
}) {
  if (!signals.length) {
    return (
      <p className="text-sm text-muted">
        No stored BUY/SELL/WAIT signals yet. Run analysis to populate history.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left text-xs">
        <thead>
          <tr className="border-b border-line/50 text-gold-muted">
            <th className="py-2 pr-2 font-medium">Time</th>
            <th className="py-2 pr-2 font-medium">Dir</th>
            <th className="py-2 pr-2 font-medium">Score</th>
            <th className="py-2 pr-2 font-medium">Entry</th>
            <th className="py-2 pr-2 font-medium">SL</th>
            <th className="py-2 pr-2 font-medium">TP</th>
            <th className="py-2 pr-2 font-medium">RR</th>
            <th className="py-2 pr-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.signal_id} className="border-b border-line/30 text-cream/90">
              <td className="py-2 pr-2 whitespace-nowrap">
                {formatTime(s.timestamp)}
              </td>
              <td
                className={`py-2 pr-2 font-semibold ${
                  s.direction === "BUY"
                    ? "text-bull"
                    : s.direction === "SELL"
                      ? "text-bear"
                      : "text-wait"
                }`}
              >
                {s.direction === "NO_TRADE" ? "NO TRADE" : s.direction}
              </td>
              <td className="py-2 pr-2">{s.score}</td>
              <td className="py-2 pr-2">
                {s.entry ? formatPrice(s.entry.preferred) : "—"}
              </td>
              <td className="py-2 pr-2">
                {s.stop_loss != null ? formatPrice(s.stop_loss) : "—"}
              </td>
              <td className="py-2 pr-2">
                {s.targets[0] ? formatPrice(s.targets[0].price) : "—"}
              </td>
              <td className="py-2 pr-2">
                {s.primary_rr != null ? s.primary_rr.toFixed(2) : "—"}
              </td>
              <td className="py-2 pr-2">{s.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 break-words text-right text-cream">{value}</span>
    </div>
  );
}

/** When spot has left the SMC entry zone, BUY/SELL is a pullback plan — not a market fill. */
function entryDistanceNote(
  signal: string,
  entry: { low: number; high: number; preferred: number } | null,
  spot: number | null,
): { title: string; detail: string } | null {
  if (spot == null || entry == null) return null;
  if (signal !== "BUY" && signal !== "SELL") return null;
  const lo = Math.min(entry.low, entry.high);
  const hi = Math.max(entry.low, entry.high);
  const pad = Math.max((hi - lo) * 0.25, Math.abs(spot) * 0.0005);
  const inZone = spot >= lo - pad && spot <= hi + pad;
  if (inZone) return null;

  if (signal === "BUY" && spot > hi + pad) {
    const gap = spot - hi;
    return {
      title: "Pullback / limit entry — not a market buy at spot",
      detail: `Spot ${formatPrice(spot)} is ~${formatPrice(gap)} above the FVG/OB zone ${formatPrice(lo)}–${formatPrice(hi)}. Wait for price to revisit the zone (or skip). Do not chase at ${formatPrice(spot)}.`,
    };
  }
  if (signal === "SELL" && spot < lo - pad) {
    const gap = lo - spot;
    return {
      title: "Pullback / limit entry — not a market sell at spot",
      detail: `Spot ${formatPrice(spot)} is ~${formatPrice(gap)} below the supply/OB zone ${formatPrice(lo)}–${formatPrice(hi)}. Wait for price to revisit the zone (or skip). Do not chase at ${formatPrice(spot)}.`,
    };
  }
  return null;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

/** Full local stamp for when a trade suggestion was produced. */
export function formatSuggestTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  } catch {
    return iso.slice(0, 19);
  }
}
