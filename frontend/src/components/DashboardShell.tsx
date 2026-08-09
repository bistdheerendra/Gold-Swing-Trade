import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  Activity,
  AlertTriangle,
  CircleDot,
  Menu,
  Shield,
  Sparkles,
  Waves,
  X,
} from "lucide-react";
import {
  CandlestickChartView,
  OhlcBanner,
  type OhlcReadout,
} from "./charts/CandlestickChart";
import { EmaToggleBar } from "./charts/EmaToggleBar";
import { TimeframeSelector } from "./TimeframeSelector";
import { SymbolSelector } from "./SymbolSelector";
import {
  fetchHealth,
  fetchMtfAnalyze,
  fetchSmcAnalyze,
  fetchStrategyAnalyze,
  fetchStrategyHistory,
  fetchTaAnalyze,
  loadChartBars,
  type HealthResponse,
  type MtfAnalyzeResponse,
  type OHLCVBar,
  type SmcAnalyzeResponse,
  type StrategyAnalyzeResponse,
  type StrategySignalDto,
  type TaAnalyzeResponse,
  type Timeframe,
} from "../lib/api";
import { AiLoader } from "./AiLoader";
import { MultiTimeframePanel } from "./MultiTimeframePanel";
import { SignalCard, SignalHistoryTable } from "./SignalCard";
import { CombinedSignalPanel } from "./CombinedSignalPanel";
import { RiskPanel } from "./RiskPanel";
import { formatPrice } from "../lib/chartData";
import { type EmaPeriod } from "../lib/ema";
import { DEFAULT_SYMBOL, symbolLabel, type TradeSymbol } from "../lib/symbols";
import {
  DEFAULT_SMC_OVERLAYS,
  type SmcOverlayKey,
  type SmcOverlayVisibility,
} from "../lib/smcTheme";

const smcToggleDefs: { id: SmcOverlayKey; label: string }[] = [
  { id: "swing", label: "Swing High/Low" },
  { id: "bos", label: "BOS" },
  { id: "choch", label: "CHoCH" },
  { id: "fvg", label: "FVG" },
  { id: "ob", label: "Order Block" },
  { id: "zones", label: "Demand/Supply" },
  { id: "liq", label: "Liquidity" },
  { id: "sweep", label: "Liquidity Sweep" },
];

const initialEmaVisibility: Record<EmaPeriod, boolean> = {
  20: true,
  50: true,
  100: false,
  200: false,
};

export function DashboardShell({
  onOpenBacktest,
  onOpenMlDataset,
  onOpenMlLab,
  onOpenRisk,
}: {
  onOpenBacktest?: () => void;
  onOpenMlDataset?: () => void;
  onOpenMlLab?: () => void;
  onOpenRisk?: () => void;
}) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [toggles, setToggles] = useState<SmcOverlayVisibility>({ ...DEFAULT_SMC_OVERLAYS });
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [symbol, setSymbol] = useState<TradeSymbol>(DEFAULT_SYMBOL);
  const [bars, setBars] = useState<OHLCVBar[]>([]);
  const [chartLoading, setChartLoading] = useState(true);
  const [chartError, setChartError] = useState<string | null>(null);
  const [ohlc, setOhlc] = useState<OhlcReadout>({
    time: null,
    open: null,
    high: null,
    low: null,
    close: null,
  });
  const [emaVisibility, setEmaVisibility] =
    useState<Record<EmaPeriod, boolean>>(initialEmaVisibility);
  const [ta, setTa] = useState<TaAnalyzeResponse | null>(null);
  const [smc, setSmc] = useState<SmcAnalyzeResponse | null>(null);
  const [mtf, setMtf] = useState<MtfAnalyzeResponse | null>(null);
  const [strategy, setStrategy] = useState<StrategyAnalyzeResponse | null>(null);
  const [signalHistory, setSignalHistory] = useState<StrategySignalDto[]>([]);
  const [navOpen, setNavOpen] = useState(false);
  const chartHeight = useResponsiveChartHeight();

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setHealthError(err instanceof Error ? err.message : "API unreachable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setChartLoading(true);
    setChartError(null);

    const load = async () => {
      try {
        // Chart bars first — never blank the chart if TA/SMC overlays fail
        const data = await loadChartBars(timeframe, {
          limit: 500,
          seedBars: 400,
          symbol,
        });
        if (cancelled) return;
        setBars(data.bars);
        const last = data.bars[data.bars.length - 1];
        if (last) {
          setOhlc({
            time: last.timestamp,
            open: last.open,
            high: last.high,
            low: last.low,
            close: last.close,
          });
        }

        const settled = await Promise.allSettled([
          fetchTaAnalyze(timeframe, { limit: 500, symbol }),
          fetchSmcAnalyze(timeframe, { limit: 500, symbol }),
          fetchMtfAnalyze({ limit: 400, symbol }),
          fetchStrategyAnalyze({ limit: 400, symbol }),
          fetchStrategyHistory({ limit: 25, symbol }),
        ]);
        if (cancelled) return;

        const [taRes, smcRes, mtfRes, strategyRes, histRes] = settled;
        setTa(taRes.status === "fulfilled" ? taRes.value : null);
        setSmc(smcRes.status === "fulfilled" ? smcRes.value : null);
        setMtf(mtfRes.status === "fulfilled" ? mtfRes.value : null);
        setStrategy(strategyRes.status === "fulfilled" ? strategyRes.value : null);
        setSignalHistory(
          histRes.status === "fulfilled" ? histRes.value.signals : [],
        );

        const overlayErrors = settled
          .slice(0, 4)
          .filter((r) => r.status === "rejected")
          .map((r) => (r as PromiseRejectedResult).reason)
          .map((err) => (err instanceof Error ? err.message : String(err)));
        if (overlayErrors.length === 4) {
          setChartError(
            `Overlays unavailable (is backend Phase 11 running?): ${overlayErrors[0]}`,
          );
        } else {
          setChartError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setBars([]);
          setTa(null);
          setSmc(null);
          setMtf(null);
          setStrategy(null);
          setSignalHistory([]);
          setChartError(
            err instanceof Error ? err.message : "Failed to load chart data",
          );
        }
      } finally {
        if (!cancelled) setChartLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [timeframe, symbol]);

  const lastClose = useMemo(() => {
    const last = bars[bars.length - 1];
    return last?.close ?? null;
  }, [bars]);

  const onEmaToggle = useCallback((period: EmaPeriod, visible: boolean) => {
    setEmaVisibility((prev) => ({ ...prev, [period]: visible }));
  }, []);

  const openPage = (fn?: () => void) => {
    setNavOpen(false);
    fn?.();
  };

  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="border-b border-line/70 bg-ink-soft/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 px-3 py-3 sm:px-4 sm:py-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3 sm:gap-4">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-gold/40 bg-gradient-to-br from-gold/30 to-gold-deep/20 shadow-[0_0_24px_rgba(212,175,55,0.18)] sm:h-11 sm:w-11">
              <Sparkles className="h-5 w-5 text-gold-bright" />
            </div>
            <div className="min-w-0">
              <p className="font-display text-xl font-semibold tracking-wide text-gold-bright sm:text-2xl">
                Gold Swing AI
              </p>
              <p className="truncate text-[10px] uppercase tracking-[0.18em] text-gold-muted sm:text-xs sm:tracking-[0.22em]">
                Decision Support · No Auto Execution
              </p>
            </div>
          </div>

          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2 text-sm xl:flex">
              <StatusChip
                label="API"
                value={health ? "Online" : healthError ? "Offline" : "Checking"}
                tone={health ? "bull" : healthError ? "bear" : "wait"}
              />
              <StatusChip label="Phase" value="11 · Risk" tone="wait" />
              <StatusChip label="Symbol" value={symbol} tone="gold" />
            </div>
            <StatusChip
              label="API"
              value={health ? "Online" : healthError ? "Offline" : "Checking"}
              tone={health ? "bull" : healthError ? "bear" : "wait"}
              className="hidden sm:inline-flex xl:hidden"
            />
            <SymbolSelector value={symbol} onChange={setSymbol} />
            <div className="hidden items-center gap-2 lg:flex">
              {onOpenBacktest ? (
                <NavPill onClick={onOpenBacktest}>Backtest</NavPill>
              ) : null}
              {onOpenMlDataset ? (
                <NavPill onClick={onOpenMlDataset}>ML Dataset</NavPill>
              ) : null}
              {onOpenMlLab ? (
                <NavPill onClick={onOpenMlLab}>ML Model Lab</NavPill>
              ) : null}
              {onOpenRisk ? (
                <NavPill onClick={onOpenRisk}>Risk Management</NavPill>
              ) : null}
            </div>
            <button
              type="button"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line/80 text-gold-bright hover:border-gold/50 lg:hidden"
              aria-label={navOpen ? "Close menu" : "Open menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((o) => !o)}
            >
              {navOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {navOpen ? (
          <div className="border-t border-line/50 bg-ink-soft/95 px-3 py-3 sm:px-4 lg:hidden md:px-6">
            <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2 xl:hidden">
                <StatusChip
                  label="API"
                  value={health ? "Online" : healthError ? "Offline" : "Checking"}
                  tone={health ? "bull" : healthError ? "bear" : "wait"}
                  className="sm:hidden"
                />
                <StatusChip label="Phase" value="11 · Risk" tone="wait" />
                <StatusChip label="Symbol" value={symbol} tone="gold" />
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                {onOpenBacktest ? (
                  <NavPill className="w-full sm:w-auto" onClick={() => openPage(onOpenBacktest)}>
                    Backtest
                  </NavPill>
                ) : null}
                {onOpenMlDataset ? (
                  <NavPill className="w-full sm:w-auto" onClick={() => openPage(onOpenMlDataset)}>
                    ML Dataset
                  </NavPill>
                ) : null}
                {onOpenMlLab ? (
                  <NavPill className="w-full sm:w-auto" onClick={() => openPage(onOpenMlLab)}>
                    ML Model Lab
                  </NavPill>
                ) : null}
                {onOpenRisk ? (
                  <NavPill className="w-full sm:w-auto" onClick={() => openPage(onOpenRisk)}>
                    Risk Management
                  </NavPill>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </header>

      <main className="mx-auto max-w-[1440px] space-y-4 px-3 py-4 sm:space-y-5 sm:px-4 sm:py-5 md:px-6">
        <Panel
          title="Price Chart"
          action={
            <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
              <span className="hidden text-[10px] uppercase tracking-wider text-gold-muted sm:inline">
                {bars[0]?.source === "delta_india"
                  ? "Delta India · live"
                  : bars[0]?.source
                    ? `${bars[0].source}`
                    : "Loading…"}
              </span>
              <TimeframeSelector
                value={timeframe}
                onChange={setTimeframe}
                disabled={chartLoading}
              />
            </div>
          }
        >
          <OhlcBanner readout={ohlc} fallbackClose={lastClose} />
          <div className="relative overflow-hidden rounded-xl border border-line/60 bg-ink">
            {chartLoading ? (
              <div
                className="grid place-items-center"
                style={{ height: chartHeight }}
              >
                <AiLoader label={`Loading ${timeframe} market data`} size="lg" />
              </div>
            ) : chartError ? (
              <div
                className="grid place-items-center px-4 text-center text-sm text-bear sm:px-6"
                style={{ height: chartHeight }}
              >
                {chartError}
              </div>
            ) : bars.length === 0 ? (
              <div
                className="grid place-items-center text-sm text-muted"
                style={{ height: chartHeight }}
              >
                No bars available for {timeframe}.
              </div>
            ) : (
              <CandlestickChartView
                bars={bars}
                height={chartHeight}
                showEma={emaVisibility}
                smc={smc}
                smcVisibility={toggles}
                onCrosshairOhlc={setOhlc}
                className="w-full"
              />
            )}
          </div>
          <p className="mt-2 text-[11px] text-gold-muted">
            Scroll to zoom · drag to pan · crosshair shows OHLC. SMC overlays use
            confirmed events only (no look-ahead).
          </p>
        </Panel>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
          <MiniStat
            icon={<Activity className="h-4 w-4" />}
            label="Signal"
            value={
              strategy?.signal === "NO_TRADE"
                ? "NO TRADE"
                : (strategy?.signal ?? "—")
            }
          />
          <MiniStat
            icon={<Shield className="h-4 w-4" />}
            label="Strategy Score"
            value={strategy ? `${strategy.score}/100` : "—"}
          />
          <MiniStat icon={<Waves className="h-4 w-4" />} label="ML Prob." value="—" />
        </div>

        {/* Equal columns — indicators + decisions sit centered, no empty mid gap */}
        <div className="grid items-start gap-4 md:grid-cols-2 lg:grid-cols-3">
          <aside className="min-w-0 space-y-4">
            <Panel title="Market Overview">
              <MetricRow label="Instrument" value={symbolLabel(symbol)} />
              <MetricRow
                label="Price"
                value={formatPrice(ohlc.close ?? lastClose)}
                hint={`${bars.length} bars · ${timeframe}`}
              />
              <MetricRow
                label="Bias"
                value={mtf?.higher_timeframe_bias ?? "WAIT"}
                accent="wait"
              />
              <MetricRow label="Timeframe" value={timeframe.toUpperCase()} />
            </Panel>

            <Panel title="Multi-Timeframe Analysis">
              <MultiTimeframePanel data={mtf} />
            </Panel>

            <Panel title="SMC Analysis">
              {smc ? (
                <div className="space-y-2">
                  <MetricRow label="Structure" value={smc.summary.structure} />
                  <MetricRow label="Last BOS" value={smc.summary.last_bos ?? "None"} />
                  <MetricRow label="Last CHoCH" value={smc.summary.last_choch ?? "None"} />
                  <MetricRow label="Liquidity" value={smc.summary.liquidity ?? "None"} />
                  <MetricRow label="FVG" value={smc.summary.fvg ?? "None"} />
                  <MetricRow
                    label="Order Block"
                    value={smc.summary.order_block ?? "None"}
                  />
                  <MetricRow label="Dealing Range" value={smc.summary.dealing_range} />
                  <MetricRow label="SMC Score" value={`${smc.smc_score}/100`} />
                </div>
              ) : (
                <div className="py-4">
                  <AiLoader label="Loading SMC" size="sm" />
                </div>
              )}
            </Panel>
          </aside>

          <aside className="min-w-0 space-y-4">
            <Panel title="SMC Overlays">
              <p className="mb-2 text-[11px] text-gold-muted">
                Detection is causal — confirmed events only. No trade signal yet.
              </p>
              <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                {smcToggleDefs.map((item) => (
                  <label
                    key={item.id}
                    className="flex cursor-pointer items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm text-cream/90 hover:bg-panel-elevated"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <CircleDot className="h-3.5 w-3.5 shrink-0 text-gold-muted" />
                      <span className="truncate">{item.label}</span>
                    </span>
                    <input
                      type="checkbox"
                      className="accent-gold"
                      checked={Boolean(toggles[item.id])}
                      onChange={() => {
                        const id = item.id;
                        startTransition(() => {
                          setToggles((prev) => ({
                            ...prev,
                            [id]: !prev[id],
                          }));
                        });
                      }}
                    />
                  </label>
                ))}
              </div>
            </Panel>

            <Panel title="TA Snapshot">
              {ta ? (
                <div className="space-y-2">
                  <MetricRow label="RSI" value={formatPrice(ta.latest.rsi)} />
                  <MetricRow label="ADX" value={formatPrice(ta.latest.adx)} />
                  <MetricRow label="ATR" value={formatPrice(ta.latest.atr)} />
                  <MetricRow
                    label="MACD"
                    value={
                      ta.latest.macd == null
                        ? "—"
                        : `${formatPrice(ta.latest.macd)} / ${formatPrice(ta.latest.macd_signal)}`
                    }
                  />
                  <MetricRow label="BB mid" value={formatPrice(ta.latest.bb_mid)} />
                  <MetricRow
                    label="Swing H"
                    value={
                      ta.structure.last_swing_high
                        ? `${formatPrice(ta.structure.last_swing_high.price)}${
                            ta.structure.last_swing_high.label
                              ? ` · ${ta.structure.last_swing_high.label}`
                              : ""
                          }`
                        : "—"
                    }
                  />
                  <MetricRow
                    label="Swing L"
                    value={
                      ta.structure.last_swing_low
                        ? `${formatPrice(ta.structure.last_swing_low.price)}${
                            ta.structure.last_swing_low.label
                              ? ` · ${ta.structure.last_swing_low.label}`
                              : ""
                          }`
                        : "—"
                    }
                  />
                </div>
              ) : (
                <div className="py-4">
                  <AiLoader label="Loading indicators" size="sm" />
                </div>
              )}
            </Panel>

            <Panel title="EMA Overlays">
              <EmaToggleBar visibility={emaVisibility} onChange={onEmaToggle} />
            </Panel>

            <Panel title="Signal History">
              <SignalHistoryTable signals={signalHistory} />
            </Panel>
          </aside>

          <aside className="min-w-0 space-y-4 md:col-span-2 lg:col-span-1">
            <Panel title="Current Signal">
              <SignalCard data={strategy} symbolLabel={symbolLabel(symbol)} />
            </Panel>

            <Panel title="Combined Signal (Rule + ML)">
              <CombinedSignalPanel modelId={undefined} symbol={symbol} />
            </Panel>

            <Panel title="Explainability">
              <div className="space-y-3 text-sm">
                <div className="flex gap-2 text-muted">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
                  <p>
                    Rule + ML filter is research-only. ML confidence is not a
                    guaranteed win probability. No broker execution.
                  </p>
                </div>
                {healthError ? (
                  <p className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2 text-bear">
                    Backend: {healthError}. Start API with{" "}
                    <code className="text-cream">uvicorn</code> to connect.
                  </p>
                ) : health ? (
                  <p className="rounded-lg border border-bull/30 bg-bull/10 px-3 py-2 text-bull">
                    Connected · strategy {health.strategy_version} · model{" "}
                    {health.model_version}
                  </p>
                ) : (
                  <p className="text-muted">Checking API health…</p>
                )}
              </div>
            </Panel>
          </aside>
        </div>

        <section className="w-full min-w-0">
          <Panel title="Risk & Position">
            <RiskPanel symbol={symbol} />
          </Panel>
        </section>
      </main>
    </div>
  );
}

function useResponsiveChartHeight(): number {
  const [height, setHeight] = useState(() =>
    typeof window !== "undefined" ? chartHeightForWidth(window.innerWidth) : 420,
  );

  useEffect(() => {
    const onResize = () => setHeight(chartHeightForWidth(window.innerWidth));
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return height;
}

function chartHeightForWidth(width: number): number {
  if (width < 640) return 280;
  if (width < 1024) return 360;
  return 420;
}

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-line/70 bg-panel/80 p-3 shadow-[inset_0_1px_0_rgba(240,215,140,0.06)] backdrop-blur-sm sm:p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-muted">
          {title}
        </h2>
        {action ? <div className="min-w-0 max-w-full">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

function MetricRow({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: "wait" | "bull" | "bear";
}) {
  const valueClass =
    accent === "wait"
      ? "text-wait"
      : accent === "bull"
        ? "text-bull"
        : accent === "bear"
          ? "text-bear"
          : "text-cream";
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/40 py-2 last:border-0">
      <div className="min-w-0 shrink">
        <p className="text-sm text-muted">{label}</p>
        {hint ? <p className="truncate text-[11px] text-gold-muted/80">{hint}</p> : null}
      </div>
      <p className={`max-w-[60%] break-words text-right text-sm font-semibold ${valueClass}`}>
        {value}
      </p>
    </div>
  );
}

function MiniStat({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-line/70 bg-panel/80 p-3 sm:p-4">
      <div className="mb-2 flex items-center gap-2 text-gold-muted">
        {icon}
        <span className="text-xs uppercase tracking-[0.16em]">{label}</span>
      </div>
      <p className="break-words font-display text-xl text-gold-bright sm:text-2xl">
        {value}
      </p>
    </div>
  );
}

function StatusChip({
  label,
  value,
  tone,
  className = "",
}: {
  label: string;
  value: string;
  tone: "bull" | "bear" | "wait" | "gold";
  className?: string;
}) {
  const toneClass =
    tone === "bull"
      ? "border-bull/40 text-bull"
      : tone === "bear"
        ? "border-bear/40 text-bear"
        : tone === "wait"
          ? "border-wait/40 text-wait"
          : "border-gold/40 text-gold-bright";
  return (
    <div
      className={`inline-flex shrink-0 rounded-full border px-2.5 py-1 sm:px-3 ${toneClass} ${className}`}
    >
      <span className="mr-1.5 text-[10px] uppercase tracking-[0.16em] opacity-70 sm:mr-2">
        {label}
      </span>
      <span className="text-xs font-semibold">{value}</span>
    </div>
  );
}

function NavPill({
  children,
  onClick,
  className = "",
}: {
  children: ReactNode;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border border-gold/40 px-3 py-1.5 text-center text-xs font-semibold text-gold-bright hover:bg-gold/10 ${className}`}
    >
      {children}
    </button>
  );
}
