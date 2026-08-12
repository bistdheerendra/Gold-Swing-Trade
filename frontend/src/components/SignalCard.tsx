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
}: {
  data: StrategyAnalyzeResponse | null;
  symbolLabel?: string;
}) {
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
  const title = symbolLabel ?? data.symbol ?? "XAUUSD";
  const levelsAreCandidates =
    data.signal === "NO_TRADE" || data.signal === "WAIT";
  const hasAnyLevel =
    data.entry != null ||
    data.stop_loss != null ||
    (data.targets?.length ?? 0) > 0;

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
        {data.signal === "WAIT" && data.reasons[0] ? (
          <p className="mt-3 text-sm text-muted">{data.reasons[0]}</p>
        ) : null}
        {data.signal === "NO_TRADE" && data.reasons[0] ? (
          <p className="mt-3 text-sm text-muted">{data.reasons[0]}</p>
        ) : null}
      </div>

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
      </div>

      <div className="space-y-1 border-t border-line/40 pt-3 text-sm">
        <Row label="HTF Bias" value={data.market_context.htf_bias} />
        <Row label="Setup" value={data.market_context.setup_bias} />
        <Row label="Entry TF" value={data.market_context.entry_bias} />
        <Row label="MTF State" value={data.market_context.state} />
        <Row label="Status" value={data.status} />
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
          Reasons
        </p>
        <ul className="space-y-1.5 text-sm text-cream/90">
          {(data.reasons.length ? data.reasons : ["—"]).map((r) => (
            <li key={r} className="leading-snug">
              {r}
            </li>
          ))}
        </ul>
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
