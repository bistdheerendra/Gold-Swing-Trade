import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import App from "./App";

vi.mock("./lib/api", () => ({
  TIMEFRAMES: ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
  fetchHealth: vi.fn().mockResolvedValue({
    status: "healthy",
    service: "Gold Swing AI",
    phase: "11.12",
    timestamp: "2026-08-08T00:00:00Z",
    symbol: "PAXGUSD",
    strategy_version: "1.0.0",
    model_version: "none",
  }),
  listMlModels: vi.fn().mockResolvedValue({ count: 0, models: [] }),
  loadChartBars: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    timeframe: "1h",
    count: 3,
    bars: [
      {
        timestamp: "2024-01-01T00:00:00+00:00",
        symbol: "PAXGUSD",
        timeframe: "1h",
        open: 2300,
        high: 2305,
        low: 2295,
        close: 2302,
        volume: 1000,
        source: "mock",
      },
      {
        timestamp: "2024-01-01T01:00:00+00:00",
        symbol: "PAXGUSD",
        timeframe: "1h",
        open: 2302,
        high: 2308,
        low: 2300,
        close: 2306,
        volume: 1100,
        source: "mock",
      },
      {
        timestamp: "2024-01-01T02:00:00+00:00",
        symbol: "PAXGUSD",
        timeframe: "1h",
        open: 2306,
        high: 2310,
        low: 2304,
        close: 2309,
        volume: 1200,
        source: "mock",
      },
    ],
  }),
  fetchTaAnalyze: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    timeframe: "1h",
    bar_count: 3,
    latest: {
      ema_20: 2305,
      ema_50: 2300,
      rsi: 55.2,
      macd: 0.4,
      macd_signal: 0.2,
      adx: 22.1,
      atr: 4.5,
      bb_upper: 2312,
      bb_mid: 2305,
      bb_lower: 2298,
    },
    structure: {
      recent_labels: ["higher_high"],
      last_swing_high: { price: 2310, label: "higher_high" },
      last_swing_low: { price: 2295, label: "higher_low" },
    },
  }),
  fetchSmcAnalyze: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    timeframe: "1h",
    bar_count: 3,
    smc_score: 55,
    structure: { bias: "BULLISH", swing_highs: [], swing_lows: [] },
    bos: [],
    choch: [],
    fvg: [],
    order_blocks: [],
    demand_zones: [],
    supply_zones: [],
    liquidity: [],
    liquidity_sweeps: [],
    dealing_range: { zone: "DISCOUNT" },
    summary: {
      structure: "BULLISH",
      last_bos: "BULLISH",
      last_choch: null,
      liquidity: null,
      fvg: "Bullish FVG active",
      order_block: null,
      dealing_range: "DISCOUNT",
      smc_score: 55,
    },
  }),
  fetchMtfAnalyze: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    as_of: "2024-01-01T00:00:00Z",
    timeframes: {
      "1d": { timeframe: "1d", trend: "BULLISH", smc_bias: "BULLISH", bias_score: 70, structure: "BULLISH" },
      "4h": { timeframe: "4h", trend: "BULLISH", smc_bias: "BULLISH", bias_score: 60, structure: "BULLISH" },
      "1h": { timeframe: "1h", trend: "BULLISH", smc_bias: "BULLISH", bias_score: 55, structure: "BULLISH" },
      "30m": { timeframe: "30m", trend: "BULLISH", smc_bias: "BULLISH", bias_score: 40, structure: "BULLISH" },
      "15m": { timeframe: "15m", trend: "NEUTRAL", smc_bias: "BULLISH", bias_score: 10, structure: "NEUTRAL" },
    },
    higher_timeframe_bias: "BULLISH",
    setup_bias: "BULLISH",
    entry_bias: "NEUTRAL",
    alignment_score: 75,
    state: "PULLBACK",
    macro: { bias: "BULLISH", timeframe: "1d", bias_score: 70 },
    structure: { bias: "BULLISH", timeframe: "4h", bias_score: 60 },
    setup: { bias: "BULLISH", timeframe: "1h", bias_score: 55 },
    timing: { bias: "BULLISH", timeframe: "30m", bias_score: 40 },
    entry: { bias: "NEUTRAL", timeframe: "15m", bias_score: 10 },
  }),
  fetchStrategyAnalyze: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    as_of: "2024-01-01T00:00:00Z",
    signal: "WAIT",
    score: 58,
    score_label: "58/100 strategy condition score",
    status: "DETECTED",
    entry: null,
    stop_loss: null,
    targets: [],
    primary_rr: null,
    market_context: {
      htf_bias: "BULLISH",
      setup_bias: "BULLISH",
      entry_bias: "NEUTRAL",
      state: "PULLBACK",
      alignment_score: 75,
    },
    conditions: [],
    reasons: ["⏳ Waiting: 15M Confirmation — incomplete"],
    risks: ["⚠ Entry timeframe confirmation incomplete"],
    volatility: "NORMAL",
    market_condition: "NORMAL",
    strategy_version: "1.0.0",
    notes: [],
  }),
  fetchStrategyHistory: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    count: 0,
    signals: [],
  }),
  fetchCombinedAnalyze: vi.fn().mockResolvedValue({
    symbol: "PAXGUSD",
    as_of: "2024-01-01T00:00:00Z",
    direction: "WAIT",
    rule_signal: "WAIT",
    rule_score: 58,
    ml_prediction: "WAIT",
    ml_confidence: 0.62,
    ml_status: "LOW_CONFIDENCE",
    probability_calibrated: false,
    targets: [],
    reasons: [],
    risks: [],
    rule_reasons: [],
    ml_reasons: [],
    notes: [],
  }),
  fetchRiskAnalyze: vi.fn().mockResolvedValue({
    label: "RESEARCH ONLY — not live execution",
    trade_plan: {
      instrument: "PAXGUSD",
      direction: "WAIT",
      signal_status: "WAIT",
      entry: null,
      stop_loss: null,
      targets: [],
      account_balance: 30000,
      currency: "INR",
      risk_percent: 1,
      risk_amount: 300,
      quantity: 0,
      notional_value: 0,
      leverage: 5,
      required_margin: 0,
      estimated_total_cost: 0,
      gross_rr: null,
      net_rr: null,
      risk_status: "SKIPPED_NO_SIGNAL",
      reasons: ["No trade setup"],
      risks: [],
      notes: [],
    },
  }),
  fetchRiskConfig: vi.fn().mockResolvedValue({
    account: {
      account_balance: 30000,
      risk_per_trade_pct: 1,
      default_leverage: 5,
      minimum_rr: 1.5,
      max_total_exposure_pct: 30,
      max_daily_loss_pct: 3,
      max_consecutive_losses: 4,
    },
    default_instrument: "PAXGUSD",
    instruments: [],
    notes: [],
  }),
  putRiskConfig: vi.fn(),
  runRiskBacktest: vi.fn(),
  fetchTradingSessions: vi.fn().mockResolvedValue({
    timezone_display: "IST",
    utc_offset_minutes: 330,
    as_of: "2024-01-01T00:00:00Z",
    active: ["asia"],
    sessions: [
      {
        id: "asia",
        name: "Asia",
        ist_window: "5:30 AM – 2:30 PM",
        utc_start_minute: 0,
        utc_end_minute: 540,
        utc_window: "00:00–09:00 UTC",
        behavior: "Often range-bound / lower volatility",
        color: "#3b82f6",
        emoji: "🟦",
        chart_fill: "rgba(59, 130, 246, 0.12)",
        priority: 1,
        window_mode: "fixed_utc",
      },
      {
        id: "london",
        name: "London",
        ist_window: "1:30 PM – 10:30 PM",
        utc_start_minute: 480,
        utc_end_minute: 1020,
        utc_window: "08:00–17:00 UTC",
        behavior: "Volatility increases",
        color: "#eab308",
        emoji: "🟨",
        chart_fill: "rgba(234, 179, 8, 0.12)",
        priority: 2,
        window_mode: "local",
        timezone: "Europe/London",
        local_start_minute: 480,
        local_end_minute: 1020,
      },
      {
        id: "new_york",
        name: "New York",
        ist_window: "6:30 PM – 3:30 AM",
        utc_start_minute: 780,
        utc_end_minute: 1320,
        utc_window: "13:00–22:00 UTC",
        behavior: "One of the highest-movement windows",
        color: "#ef4444",
        emoji: "🟥",
        chart_fill: "rgba(239, 68, 68, 0.14)",
        priority: 3,
        window_mode: "local",
        timezone: "America/New_York",
        local_start_minute: 480,
        local_end_minute: 1020,
      },
      {
        id: "london_ny_overlap",
        name: "London + NY Overlap",
        ist_window: "6:30 PM – 10:30 PM",
        utc_start_minute: 780,
        utc_end_minute: 1020,
        utc_window: "13:00–17:00 UTC",
        behavior: "Most significant window (highest volatility)",
        color: "#f97316",
        emoji: "🔥",
        chart_fill: "rgba(249, 115, 22, 0.22)",
        priority: 4,
        window_mode: "overlap",
      },
    ],
    band_timeframes: ["15m", "30m", "1h"],
    note: "Display/reference only",
  }),
}));

vi.mock("./components/charts/CandlestickChart", () => ({
  CandlestickChartView: () => <div data-testid="candlestick-chart">chart</div>,
  OhlcBanner: ({
    readout,
  }: {
    readout: { open: number | null; close: number | null };
  }) => (
    <div data-testid="ohlc-banner">
      O {readout.open ?? "—"} C {readout.close ?? "—"}
    </div>
  ),
}));

describe("DashboardShell Phase 11", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders brand, chart, MTF, risk panel, and strategy signal card", async () => {
    render(<App />);
    expect(screen.getByText("Gold Swing AI")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "1h" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "PAXGUSD" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "SLVONUSD" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("candlestick-chart")).toBeInTheDocument();
    });
    expect(screen.getByText(/11\.12/i)).toBeInTheDocument();
    expect(await screen.findByTestId("mtf-panel")).toBeInTheDocument();
    expect(screen.getAllByText("PULLBACK").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getAllByText(/Strategy Score/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("58/100 strategy condition score")).toBeInTheDocument();
    expect(screen.getAllByText("WAIT").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("combined-signal-panel")).toBeInTheDocument();
    expect(screen.getByTestId("risk-panel")).toBeInTheDocument();
  });
});
