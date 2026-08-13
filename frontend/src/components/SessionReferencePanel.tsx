import type { SessionDefinition } from "../lib/sessions";

type SessionReferencePanelProps = {
  sessions: readonly SessionDefinition[];
  active: readonly string[];
  asOf?: string | null;
  loading?: boolean;
  error?: string | null;
};

/**
 * Static/reference session table + live active indicator.
 * Definitions come from GET /api/market/sessions (backend single source of truth).
 */
export function SessionReferencePanel({
  sessions,
  active,
  asOf,
  loading,
  error,
}: SessionReferencePanelProps) {
  const activeSet = new Set(active);
  const activeDefs = sessions.filter((s) => activeSet.has(s.id));

  return (
    <div data-testid="session-reference-panel" className="space-y-3">
      <p className="text-[11px] leading-relaxed text-gold-muted">
        Gold / silver (PAXGUSD / SLVONUSD) volatility characteristically differs by session. Times shown
        in IST (UTC+5:30). Display only — does not affect signals.
      </p>

      {loading ? (
        <p className="text-sm text-muted">Loading sessions…</p>
      ) : error ? (
        <p className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2 text-sm text-bear">
          {error}
        </p>
      ) : (
        <>
          <div
            className="rounded-xl border border-gold/25 bg-gold/5 px-3 py-2.5"
            data-testid="session-active-now"
          >
            <p className="text-[10px] uppercase tracking-wider text-gold-muted">
              Active now
            </p>
            {activeDefs.length === 0 ? (
              <p className="mt-1 text-sm text-cream/80">No named session window</p>
            ) : (
              <ul className="mt-1.5 space-y-1">
                {activeDefs
                  .slice()
                  .sort((a, b) => b.priority - a.priority)
                  .map((s) => (
                    <li
                      key={s.id}
                      className="flex items-center gap-2 text-sm text-cream"
                    >
                      <span aria-hidden>{s.emoji}</span>
                      <span className="font-medium">{s.name}</span>
                      <span className="text-[11px] text-gold">— active now</span>
                    </li>
                  ))}
              </ul>
            )}
            {asOf ? (
              <p className="mt-1.5 text-[10px] text-muted">
                as of {new Date(asOf).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}{" "}
                IST
              </p>
            ) : null}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[280px] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-line/60 text-[10px] uppercase tracking-wider text-gold-muted">
                  <th className="py-2 pr-2 font-medium">Session</th>
                  <th className="py-2 pr-2 font-medium">IST window</th>
                  <th className="py-2 font-medium">Typical gold behavior</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const isActive = activeSet.has(s.id);
                  return (
                    <tr
                      key={s.id}
                      className={
                        isActive
                          ? "border-b border-line/40 bg-gold/10"
                          : "border-b border-line/40"
                      }
                    >
                      <td className="py-2 pr-2 align-top text-cream">
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                            style={{ backgroundColor: s.color }}
                            aria-hidden
                          />
                          <span aria-hidden>{s.emoji}</span>
                          <span className={isActive ? "font-semibold" : undefined}>
                            {s.name}
                          </span>
                        </span>
                      </td>
                      <td className="py-2 pr-2 align-top whitespace-nowrap text-muted">
                        {s.ist_window}
                      </td>
                      <td className="py-2 align-top text-cream/80">{s.behavior}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
