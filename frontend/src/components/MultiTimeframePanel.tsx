import type { MtfAnalyzeResponse } from "../lib/api";
import { AiLoader } from "./AiLoader";

const TF_ORDER = ["1d", "4h", "1h", "30m", "15m"] as const;

function tone(bias: string): string {
  if (bias === "BULLISH") return "text-bull";
  if (bias === "BEARISH") return "text-bear";
  return "text-wait";
}

function scoreText(score: number): string {
  const sign = score > 0 ? "+" : "";
  return `${sign}${score}`;
}

export function MultiTimeframePanel({ data }: { data: MtfAnalyzeResponse | null }) {
  if (!data) {
    return <AiLoader label="Loading multi-timeframe" size="sm" />;
  }

  return (
    <div className="space-y-3" data-testid="mtf-panel">
      <div className="overflow-x-auto rounded-xl border border-line/60">
        <table className="w-full min-w-[280px] text-left text-xs">
          <thead className="bg-panel-elevated text-[10px] uppercase tracking-[0.16em] text-gold-muted">
            <tr>
              <th className="px-2 py-2 font-medium sm:px-3">TF</th>
              <th className="px-2 py-2 font-medium sm:px-3">Trend</th>
              <th className="px-2 py-2 font-medium sm:px-3">SMC</th>
              <th className="px-2 py-2 font-medium sm:px-3">Score</th>
            </tr>
          </thead>
          <tbody>
            {TF_ORDER.map((tf) => {
              const row = data.timeframes[tf];
              if (!row) return null;
              return (
                <tr key={tf} className="border-t border-line/40">
                  <td className="px-2 py-2 font-semibold uppercase text-cream sm:px-3">{tf}</td>
                  <td className={`px-2 py-2 font-semibold sm:px-3 ${tone(row.trend)}`}>
                    {row.trend}
                  </td>
                  <td className={`px-2 py-2 sm:px-3 ${tone(row.smc_bias)}`}>{row.smc_bias}</td>
                  <td className={`px-2 py-2 font-semibold sm:px-3 ${tone(row.trend)}`}>
                    {scoreText(row.bias_score)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="space-y-1.5 text-sm">
        <Row label="Higher TF Bias" value={data.higher_timeframe_bias} />
        <Row label="Setup Bias" value={data.setup_bias} />
        <Row label="Entry Bias" value={data.entry_bias} />
        <Row label="Alignment" value={`${data.alignment_score}%`} plain />
        <Row label="State" value={data.state} plain />
      </div>
      <p className="text-[11px] text-gold-muted">
        Context only — not a BUY/SELL signal. Closed candles only (no HTF look-ahead).
      </p>
    </div>
  );
}

function Row({
  label,
  value,
  plain,
}: {
  label: string;
  value: string;
  plain?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line/30 py-1.5 last:border-0">
      <span className="shrink-0 text-muted">{label}</span>
      <span className={`min-w-0 break-words text-right font-semibold ${plain ? "text-cream" : tone(value)}`}>{value}</span>
    </div>
  );
}
