import { useCallback, useEffect, useState } from "react";
import {
  fetchRiskAnalyze,
  fetchRiskConfig,
  putRiskConfig,
  runRiskBacktest,
  type RiskAnalyzeResponse,
  type RiskConfigResponse,
} from "../lib/api";
import { DEFAULT_SYMBOL, type TradeSymbol } from "../lib/symbols";
import { AiLoader } from "./AiLoader";

/** Matches backend /api/risk/analyze Query(ge=0.01, le=10). */
const RISK_PCT_MIN = 0.01;
const RISK_PCT_MAX = 10;

function statusTone(status: string): string {
  if (status === "RISK_ACCEPTED") return "text-bull border-bull/40 bg-bull/10";
  if (status === "SKIPPED_NO_SIGNAL") return "text-wait border-wait/30 bg-wait/10";
  return "text-bear border-bear/40 bg-bear/10";
}

function clamp(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}

type AccountFields = RiskConfigResponse["account"];

function accountFromForm(args: {
  balance: number;
  riskPct: number;
  leverage: number;
  minRr: number;
  maxExposure: number;
  maxDailyLoss: number;
  maxConsec: number;
  base?: AccountFields | null;
}): AccountFields {
  const base = args.base ?? ({} as AccountFields);
  return {
    ...base,
    account_balance: args.balance,
    available_balance: args.balance,
    risk_per_trade_pct: clamp(args.riskPct, RISK_PCT_MIN, RISK_PCT_MAX),
    default_leverage: args.leverage,
    minimum_rr: args.minRr,
    max_total_exposure_pct: args.maxExposure,
    max_daily_loss_pct: args.maxDailyLoss,
    max_consecutive_losses: args.maxConsec,
  };
}

export function RiskPanel({ symbol }: { symbol?: TradeSymbol }) {
  const sym = symbol ?? DEFAULT_SYMBOL;
  const [balance, setBalance] = useState(30000);
  const [riskPct, setRiskPct] = useState(1);
  const [leverage, setLeverage] = useState(5);
  const [minRr, setMinRr] = useState(1.5);
  const [maxExposure, setMaxExposure] = useState(30);
  const [maxDailyLoss, setMaxDailyLoss] = useState(3);
  const [maxConsec, setMaxConsec] = useState(4);
  const [savedAccount, setSavedAccount] = useState<AccountFields | null>(null);
  const [configReady, setConfigReady] = useState(false);
  const [data, setData] = useState<RiskAnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRiskConfig()
      .then((cfg) => {
        if (cancelled) return;
        const a = cfg.account;
        setSavedAccount(a);
        setBalance(Number(a.account_balance) || 30000);
        setRiskPct(Number(a.risk_per_trade_pct) || 1);
        setLeverage(Number(a.default_leverage) || 5);
        setMinRr(Number(a.minimum_rr) || 1.5);
        setMaxExposure(Number(a.max_total_exposure_pct) || 30);
        setMaxDailyLoss(Number(a.max_daily_loss_pct) || 3);
        setMaxConsec(Number(a.max_consecutive_losses) || 4);
        setConfigReady(true);
      })
      .catch(() => {
        if (!cancelled) setConfigReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const recalculate = useCallback(async () => {
    if (!(balance > 0)) {
      setError("Account balance must be greater than 0.");
      return;
    }
    if (riskPct < RISK_PCT_MIN || riskPct > RISK_PCT_MAX) {
      setError(
        `Risk % must be between ${RISK_PCT_MIN} and ${RISK_PCT_MAX} (you entered ${riskPct}).`,
      );
      return;
    }
    if (!(leverage > 0)) {
      setError("Leverage must be greater than 0.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Persist protection + account fields so analyze uses the same config.
      const account = accountFromForm({
        balance,
        riskPct,
        leverage,
        minRr,
        maxExposure,
        maxDailyLoss,
        maxConsec,
        base: savedAccount,
      });
      const updated = await putRiskConfig(account);
      setSavedAccount(updated.account);

      const res = await fetchRiskAnalyze({
        symbol: sym,
        account_balance: balance,
        risk_percent: clamp(riskPct, RISK_PCT_MIN, RISK_PCT_MAX),
        leverage,
        minimum_rr: minRr,
        mode: "ML_FILTER",
      });
      setData(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Risk analyze failed");
    } finally {
      setLoading(false);
    }
  }, [
    sym,
    balance,
    riskPct,
    leverage,
    minRr,
    maxExposure,
    maxDailyLoss,
    maxConsec,
    savedAccount,
  ]);

  useEffect(() => {
    if (!configReady) return;
    void recalculate();
    // Seed once after config load — avoid re-running on every field keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configReady, sym]);

  const plan = data?.trade_plan;

  return (
    <div className="space-y-4" data-testid="risk-panel">
      <p className="text-[11px] text-gold-muted">
        PAXGUSD risk calculator — sizes Phase 10 signals only. Never invents
        BUY/SELL. Research only. Protection limits are saved to risk config
        before each recalculate.
      </p>

      <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-2 xl:grid-cols-3">
            <label className="space-y-1">
              <span className="text-muted">Account (₹)</span>
              <input
                type="number"
                min={1}
                value={balance}
                onChange={(e) => setBalance(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1">
              <span className="text-muted">Risk % (max {RISK_PCT_MAX})</span>
              <input
                type="number"
                min={RISK_PCT_MIN}
                max={RISK_PCT_MAX}
                step="0.1"
                value={riskPct}
                onChange={(e) => setRiskPct(Number(e.target.value))}
                onBlur={() =>
                  setRiskPct((v) => clamp(v, RISK_PCT_MIN, RISK_PCT_MAX))
                }
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1">
              <span className="text-muted">Leverage</span>
              <input
                type="number"
                min={1}
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1">
              <span className="text-muted">Min RR</span>
              <input
                type="number"
                step="0.1"
                value={minRr}
                onChange={(e) => setMinRr(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1">
              <span className="text-muted">Max exposure %</span>
              <input
                type="number"
                value={maxExposure}
                onChange={(e) => setMaxExposure(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1">
              <span className="text-muted">Max daily loss %</span>
              <input
                type="number"
                value={maxDailyLoss}
                onChange={(e) => setMaxDailyLoss(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
            <label className="space-y-1 sm:col-span-2 md:col-span-1 lg:col-span-2 xl:col-span-1">
              <span className="text-muted">Max consecutive losses</span>
              <input
                type="number"
                value={maxConsec}
                onChange={(e) => setMaxConsec(Number(e.target.value))}
                className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
              />
            </label>
          </div>

          <button
            type="button"
            onClick={() => void recalculate()}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-gold/40 px-3 py-1.5 text-xs text-gold-bright hover:bg-gold/10 disabled:opacity-50 sm:w-auto sm:min-w-[12rem]"
          >
            {loading ? (
              <AiLoader label="Calculating" size="sm" inline />
            ) : (
              "Recalculate trade plan"
            )}
          </button>

          {error ? (
            <p className="rounded border border-bear/30 bg-bear/10 px-2 py-1 text-xs text-bear">
              {error}
            </p>
          ) : null}
        </div>

        <div className="min-w-0">
          {plan ? (
            <div className="grid gap-x-6 gap-y-0 text-xs sm:grid-cols-2">
              <div
                className={`rounded-lg border px-3 py-2 font-semibold sm:col-span-2 ${statusTone(plan.risk_status)}`}
                data-testid="risk-status"
              >
                {plan.risk_status.replace(/_/g, " ")}
              </div>
              <Row label="Instrument" value={plan.instrument} />
              <Row label="Direction" value={String(plan.direction ?? "—")} />
              <Row label="Signal" value={plan.signal_status} />
              <Row
                label="Rule score"
                value={
                  plan.rule_score != null ? String(plan.rule_score) : "—"
                }
              />
              <Row
                label="ML pred"
                value={plan.ml_prediction != null ? String(plan.ml_prediction) : "—"}
              />
              <Row
                label="ML conf"
                value={
                  plan.ml_confidence != null
                    ? `${(Number(plan.ml_confidence) * 100).toFixed(0)}%`
                    : "—"
                }
              />
              <Row label="Entry" value={plan.entry != null ? `$${plan.entry}` : "—"} />
              <Row label="SL" value={plan.stop_loss != null ? `$${plan.stop_loss}` : "—"} />
              {(plan.targets ?? []).map((t) => (
                <Row key={t.label} label={t.label} value={`$${t.price}`} />
              ))}
              <Row label="Qty" value={String(plan.quantity)} />
              <Row label="Notional" value={`$${plan.notional_value}`} />
              <Row label="Margin" value={`$${plan.required_margin}`} />
              <Row label="Est. cost" value={`$${plan.estimated_total_cost}`} />
              <Row
                label="Gross RR"
                value={plan.gross_rr != null ? String(plan.gross_rr) : "—"}
              />
              <Row
                label="Net RR"
                value={plan.net_rr != null ? String(plan.net_rr) : "—"}
              />
              {(plan.reasons ?? []).length ? (
                <div className="sm:col-span-2 mt-2 space-y-1 text-[11px] text-muted">
                  {plan.reasons.slice(0, 4).map((r) => (
                    <p key={r}>• {r}</p>
                  ))}
                </div>
              ) : null}
              {(plan.risks ?? []).length ? (
                <div className="sm:col-span-2 mt-1 space-y-1 text-[11px] text-bear/90">
                  {plan.risks.slice(0, 3).map((r) => (
                    <p key={r}>⚠ {r}</p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : loading ? (
            <div className="py-6">
              <AiLoader label="Building trade plan" size="md" />
            </div>
          ) : (
            <p className="text-sm text-muted">No trade plan yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-line/40 py-1">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 break-words text-right text-cream">{value}</span>
    </div>
  );
}

export function RiskManagementPage({ onBack }: { onBack: () => void }) {
  const [cfg, setCfg] = useState<RiskConfigResponse | null>(null);
  const [btNotes, setBtNotes] = useState<string[]>([]);
  const [btLoading, setBtLoading] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    void fetchRiskConfig().then(setCfg).catch(() => setCfg(null));
  }, []);

  const updateAccount = <K extends keyof AccountFields>(
    key: K,
    value: AccountFields[K],
  ) => {
    setCfg((prev) =>
      prev
        ? {
            ...prev,
            account: { ...prev.account, [key]: value },
          }
        : prev,
    );
  };

  const saveCfg = async () => {
    if (!cfg) return;
    setSaveMsg(null);
    setSaveError(null);
    try {
      const updated = await putRiskConfig(cfg.account);
      setCfg({ ...cfg, account: updated.account });
      setSaveMsg("Saved.");
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const runBt = async () => {
    setBtLoading(true);
    try {
      const res = await runRiskBacktest({
        symbol: DEFAULT_SYMBOL,
        risk_mode: "RISK_PERCENT",
        risk_fraction_per_trade: 0.01,
        initial_equity: cfg?.account.account_balance ?? 30000,
        limit: 280,
      });
      setBtNotes([
        `Trades: ${res.backtest.metrics?.total_trades ?? "—"}`,
        `Max DD%: ${res.backtest.metrics?.max_drawdown_pct ?? "—"}`,
        `Max loss streak: ${res.loss_streaks.max_consecutive_losses}`,
        res.ruin_estimate.rough_ruin_hint,
        ...res.notes,
      ]);
    } catch (e: unknown) {
      setBtNotes([e instanceof Error ? e.message : "Backtest failed"]);
    } finally {
      setBtLoading(false);
    }
  };

  const a = cfg?.account;

  return (
    <div className="min-h-screen overflow-x-hidden bg-ink px-3 py-4 text-cream sm:px-4 sm:py-6 md:px-6" data-testid="risk-page">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.2em] text-gold-muted">
              Phase 11
            </p>
            <h1 className="text-xl font-semibold text-gold-bright sm:text-2xl">
              Risk Management
            </h1>
            <p className="text-sm text-muted">
              PAXGUSD instrument-aware sizing · no live orders
            </p>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 rounded-full border border-line px-4 py-1.5 text-sm hover:border-gold/40"
          >
            Dashboard
          </button>
        </div>

        <div className="grid gap-4 sm:gap-6 lg:grid-cols-2">
          <section className="min-w-0 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
              PAXGUSD Risk Calculator
            </h2>
            <RiskPanel symbol={DEFAULT_SYMBOL} />
          </section>

          <section className="min-w-0 space-y-3 rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
              Account Protection Settings
            </h2>
            {cfg && a ? (
              <>
                <p className="text-xs text-muted">
                  Default instrument: {cfg.default_instrument}
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <label className="space-y-1">
                    <span className="text-muted">Account balance</span>
                    <input
                      type="number"
                      value={Number(a.account_balance)}
                      onChange={(e) =>
                        updateAccount("account_balance", Number(e.target.value))
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-muted">Risk % / trade</span>
                    <input
                      type="number"
                      step="0.1"
                      value={Number(a.risk_per_trade_pct)}
                      onChange={(e) =>
                        updateAccount("risk_per_trade_pct", Number(e.target.value))
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-muted">Default leverage</span>
                    <input
                      type="number"
                      value={Number(a.default_leverage)}
                      onChange={(e) =>
                        updateAccount("default_leverage", Number(e.target.value))
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-muted">Minimum RR</span>
                    <input
                      type="number"
                      step="0.1"
                      value={Number(a.minimum_rr)}
                      onChange={(e) =>
                        updateAccount("minimum_rr", Number(e.target.value))
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-muted">Max exposure %</span>
                    <input
                      type="number"
                      value={Number(a.max_total_exposure_pct)}
                      onChange={(e) =>
                        updateAccount(
                          "max_total_exposure_pct",
                          Number(e.target.value),
                        )
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-muted">Max daily loss %</span>
                    <input
                      type="number"
                      value={Number(a.max_daily_loss_pct)}
                      onChange={(e) =>
                        updateAccount("max_daily_loss_pct", Number(e.target.value))
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                  <label className="space-y-1 col-span-2">
                    <span className="text-muted">Max consecutive losses</span>
                    <input
                      type="number"
                      value={Number(a.max_consecutive_losses)}
                      onChange={(e) =>
                        updateAccount(
                          "max_consecutive_losses",
                          Number(e.target.value),
                        )
                      }
                      className="w-full rounded border border-line bg-panel px-2 py-1 text-cream"
                    />
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() => void saveCfg()}
                  className="rounded-lg border border-gold/40 px-3 py-1.5 text-xs text-gold-bright"
                >
                  Save risk config
                </button>
                {saveMsg ? (
                  <p className="text-xs text-bull">{saveMsg}</p>
                ) : null}
                {saveError ? (
                  <p className="text-xs text-bear">{saveError}</p>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted">Loading config…</p>
            )}

            <button
              type="button"
              onClick={() => void runBt()}
              disabled={btLoading}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-3 py-1.5 text-xs hover:border-gold/40 disabled:opacity-50"
            >
              {btLoading ? (
                <AiLoader label="Running" size="sm" inline />
              ) : (
                "Run RISK_PERCENT backtest sample"
              )}
            </button>
            {btNotes.length ? (
              <ul className="space-y-1 text-xs text-muted">
                {btNotes.map((n) => (
                  <li key={n}>• {n}</li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
