export type Timeframe = "15m" | "30m" | "1h" | "4h" | "1d";

export const TIMEFRAMES: Timeframe[] = ["15m", "30m", "1h", "4h", "1d"];

export type OHLCVBar = {
  timestamp: string;
  symbol: string;
  timeframe: Timeframe | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source: string;
};

export type OHLCVListResponse = {
  symbol: string;
  timeframe: string;
  count: number;
  bars: OHLCVBar[];
};

export type IngestResponse = {
  symbol: string;
  timeframe: string;
  bars_ingested: number;
};

export type HealthResponse = {
  status: string;
  service: string;
  phase: number;
  timestamp: string;
  symbol: string;
  strategy_version: string;
  model_version: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${path}`);
  }
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/api/health");
}

export async function fetchOhlcv(
  timeframe: Timeframe,
  options?: { symbol?: string; limit?: number },
): Promise<OHLCVListResponse> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(options?.limit ?? 500),
  });
  if (options?.symbol) {
    params.set("symbol", options.symbol);
  }
  return apiGet<OHLCVListResponse>(`/api/market/ohlcv?${params.toString()}`);
}

export async function seedMarketData(
  timeframe: Timeframe,
  bars = 400,
  options?: { symbol?: string; force?: boolean },
): Promise<IngestResponse> {
  const params = new URLSearchParams({
    timeframe,
    bars: String(bars),
  });
  if (options?.symbol) params.set("symbol", options.symbol);
  if (options?.force) params.set("force", "true");
  return apiPost<IngestResponse>(`/api/market/seed?${params.toString()}`);
}

/**
 * Load OHLCV for charting from the active provider (Delta India by default).
 * force refresh pulls the latest live candles into the store.
 */
export async function loadChartBars(
  timeframe: Timeframe,
  options?: { symbol?: string; limit?: number; seedBars?: number },
): Promise<OHLCVListResponse> {
  const params = new URLSearchParams({
    timeframe,
    bars: String(options?.seedBars ?? 400),
  });
  if (options?.symbol) params.set("symbol", options.symbol);
  const refresh = await fetch(`${API_BASE}/api/market/refresh?${params.toString()}`, {
    method: "POST",
  });
  if (!refresh.ok) {
    // Fallback: seed/ensure path if refresh not available
    await seedMarketData(timeframe, options?.seedBars ?? 400, {
      symbol: options?.symbol,
      force: true,
    });
  }
  return fetchOhlcv(timeframe, options);
}

export async function fetchMarketTicker(symbol?: string): Promise<{
  symbol: string;
  bid?: number | null;
  ask?: number | null;
  last?: number | null;
  spread_source?: string;
  source?: string;
}> {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  const q = params.toString();
  return apiGet(`/api/market/ticker${q ? `?${q}` : ""}`);
}

export type TaAnalyzeResponse = {
  symbol: string;
  timeframe: string;
  bar_count: number;
  latest: {
    ema_20: number | null;
    ema_50: number | null;
    rsi: number | null;
    macd: number | null;
    macd_signal: number | null;
    adx: number | null;
    atr: number | null;
    bb_upper: number | null;
    bb_mid: number | null;
    bb_lower: number | null;
  };
  structure: {
    recent_labels: string[];
    last_swing_high: { price: number; label: string | null } | null;
    last_swing_low: { price: number; label: string | null } | null;
  };
};

export async function fetchTaAnalyze(
  timeframe: Timeframe,
  options?: { symbol?: string; limit?: number },
): Promise<TaAnalyzeResponse> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(options?.limit ?? 500),
  });
  if (options?.symbol) {
    params.set("symbol", options.symbol);
  }
  return apiGet<TaAnalyzeResponse>(`/api/ta/analyze?${params.toString()}`);
}

export type SmcEventDto = {
  id: string;
  type: string;
  direction: string;
  timeframe: string;
  created_index: number;
  confirm_index: number;
  valid: boolean;
  high?: number | null;
  low?: number | null;
  price?: number | null;
  metadata?: Record<string, unknown>;
};

export type SmcAnalyzeResponse = {
  symbol: string;
  timeframe: string;
  bar_count: number;
  smc_score: number;
  structure: {
    bias: string;
    swing_highs?: SmcEventDto[];
    swing_lows?: SmcEventDto[];
  };
  bos: SmcEventDto[];
  choch: SmcEventDto[];
  fvg: Array<SmcEventDto & { lifecycle?: string; filled?: boolean }>;
  order_blocks: SmcEventDto[];
  demand_zones: SmcEventDto[];
  supply_zones: SmcEventDto[];
  liquidity: SmcEventDto[];
  liquidity_sweeps: SmcEventDto[];
  dealing_range: { zone: string; equilibrium?: number | null };
  summary: {
    structure: string;
    last_bos: string | null;
    last_choch: string | null;
    liquidity: string | null;
    fvg: string | null;
    order_block: string | null;
    dealing_range: string;
    smc_score: number;
  };
};

export async function fetchSmcAnalyze(
  timeframe: Timeframe,
  options?: { symbol?: string; limit?: number },
): Promise<SmcAnalyzeResponse> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(options?.limit ?? 500),
  });
  if (options?.symbol) {
    params.set("symbol", options.symbol);
  }
  return apiGet<SmcAnalyzeResponse>(`/api/smc/analyze?${params.toString()}`);
}

export type MtfTimeframeRow = {
  timeframe: string;
  trend: string;
  smc_bias: string;
  bias_score: number;
  structure: string;
};

export type MtfAnalyzeResponse = {
  symbol: string;
  as_of: string;
  timeframes: Record<string, MtfTimeframeRow>;
  higher_timeframe_bias: string;
  setup_bias: string;
  entry_bias: string;
  alignment_score: number;
  state: string;
  macro: { bias: string; timeframe: string; bias_score: number };
  structure: { bias: string; timeframe: string; bias_score: number };
  setup: { bias: string; timeframe: string; bias_score: number };
  entry: { bias: string; timeframe: string; bias_score: number };
};

export async function fetchMtfAnalyze(options?: {
  limit?: number;
  symbol?: string;
}): Promise<MtfAnalyzeResponse> {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 400),
  });
  if (options?.symbol) params.set("symbol", options.symbol);
  return apiGet<MtfAnalyzeResponse>(`/api/mtf/analyze?${params.toString()}`);
}

export type StrategyEntryZone = {
  low: number;
  high: number;
  preferred: number;
};

export type StrategyTarget = {
  price: number;
  rr: number;
  label: string;
};

export type StrategySignalDto = {
  signal_id: string;
  setup_id: string;
  symbol: string;
  timestamp: string;
  direction: "BUY" | "SELL" | "WAIT" | "NO_TRADE";
  status: string;
  score: number;
  entry?: StrategyEntryZone | null;
  stop_loss?: number | null;
  targets: StrategyTarget[];
  primary_rr?: number | null;
  reasons: string[];
  risks: string[];
};

export type StrategyAnalyzeResponse = {
  symbol: string;
  as_of: string;
  signal: "BUY" | "SELL" | "WAIT" | "NO_TRADE";
  score: number;
  score_label: string;
  status: string;
  setup_id?: string | null;
  signal_id?: string | null;
  entry?: StrategyEntryZone | null;
  stop_loss?: number | null;
  targets: StrategyTarget[];
  primary_rr?: number | null;
  market_context: {
    htf_bias: string;
    setup_bias: string;
    entry_bias: string;
    state: string;
    alignment_score: number;
  };
  conditions: Array<{
    key: string;
    label: string;
    met: boolean;
    points: number;
    max_points: number;
    detail: string;
  }>;
  reasons: string[];
  risks: string[];
  volatility: string;
  market_condition: string;
  strategy_version: string;
  notes: string[];
};

export type StrategyHistoryResponse = {
  symbol: string;
  count: number;
  signals: StrategySignalDto[];
};

export async function fetchStrategyAnalyze(options?: {
  limit?: number;
  symbol?: string;
}): Promise<StrategyAnalyzeResponse> {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 400),
  });
  if (options?.symbol) params.set("symbol", options.symbol);
  return apiGet<StrategyAnalyzeResponse>(
    `/api/strategy/analyze?${params.toString()}`,
  );
}

export async function fetchStrategyHistory(options?: {
  limit?: number;
  symbol?: string;
}): Promise<StrategyHistoryResponse> {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 30),
  });
  if (options?.symbol) params.set("symbol", options.symbol);
  return apiGet<StrategyHistoryResponse>(
    `/api/strategy/history?${params.toString()}`,
  );
}

export type BacktestTradeDto = {
  trade_id: string;
  signal_id: string;
  setup_id: string;
  direction: string;
  status: string;
  signal_time: string;
  entry_time?: string | null;
  entry_price?: number | null;
  stop_loss: number;
  selected_tp?: number | null;
  exit_time?: string | null;
  exit_price?: number | null;
  exit_reason?: string | null;
  net_r?: number | null;
  score: number;
  strategy_version: string;
  market_state?: string | null;
};

export type BacktestResult = {
  backtest_id: string;
  symbol: string;
  entry_timeframe: string;
  start: string;
  end: string;
  strategy_version: string;
  data_version: string;
  summary: Record<string, number | string>;
  metrics: {
    total_signals: number;
    signals_expired: number;
    trades_entered: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    net_profit_r: number;
    average_r: number;
    expectancy_r: number;
    profit_factor: number;
    max_drawdown: number;
    max_drawdown_pct: number;
    final_equity: number;
    initial_equity: number;
    total_trading_cost: number;
  };
  equity_curve: Array<{
    timestamp: string;
    bar_index: number;
    equity: number;
    drawdown: number;
    drawdown_pct: number;
    peak: number;
  }>;
  trades: BacktestTradeDto[];
  signals: unknown[];
  breakdowns: Record<
    string,
    Array<{ key: string; trades: number; wins: number; losses: number; net_r: number; win_rate: number }>
  >;
  warnings: string[];
  notes: string[];
};

export async function runBacktest(body: {
  symbol?: string;
  timeframe?: string;
  start?: string;
  end?: string;
  initial_equity?: number;
  limit?: number;
  warmup_bars?: number;
  cost_config?: Record<string, string | number>;
  execution_config?: Record<string, string | number | boolean | null>;
  split_segment?: string;
}): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE}/api/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backtest failed (${response.status}): ${text}`);
  }
  return response.json() as Promise<BacktestResult>;
}

export type MlDatasetResult = {
  dataset_id: string;
  metadata: {
    dataset_id: string;
    dataset_version: string;
    feature_version: string;
    label_version: string;
    row_count: number;
    feature_count: number;
    label_count: number;
    split: { train: number; validation: number; test: number; total: number };
    missing_value_statistics: Record<string, number>;
  };
  statistics: {
    row_count: number;
    feature_count: number;
    label_count: number;
    missing_by_feature: Record<string, number>;
    class_distribution: Record<
      string,
      Array<{ key: string; count: number; percentage: number }>
    >;
  };
  preview_rows: Array<{
    timestamp: string;
    features: Record<string, unknown>;
    labels: Record<string, unknown>;
  }>;
  output_dir: string;
};

export async function buildMlDataset(body: {
  symbol?: string;
  timeframe?: string;
  start?: string;
  end?: string;
  feature_version?: string;
  label_version?: string;
  limit?: number;
  warmup_bars?: number;
  row_step?: number;
  include_strategy?: boolean;
}): Promise<MlDatasetResult> {
  const response = await fetch(`${API_BASE}/api/ml/dataset/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Dataset build failed (${response.status}): ${text}`);
  }
  return response.json() as Promise<MlDatasetResult>;
}

export type MlTrainResult = {
  status: string;
  model_id: string;
  selected_model_type: string;
  target: string;
  train_metrics: Record<string, unknown>;
  validation_metrics: Record<string, unknown>;
  test_metrics: Record<string, unknown>;
  baselines?: Record<string, unknown>;
  overfitting?: string | null;
  feature_importance?: Array<{ feature: string; importance: number }>;
  test_filter?: {
    threshold?: number;
    rule_only?: Record<string, number>;
    rule_plus_ml?: Record<string, number>;
    tag_counts?: Record<string, number>;
    error?: string;
  };
  notes?: string[];
};

export type MlModelSummary = {
  model_id: string;
  model_type: string;
  target: string;
  status: string;
  dataset_id?: string;
  trained_at?: string;
  overfitting?: string | null;
};

export async function trainMlModel(body: {
  dataset_id: string;
  target: string;
  model_type?: string;
  random_seed?: number;
  run_test?: boolean;
}): Promise<MlTrainResult> {
  const response = await fetch(`${API_BASE}/api/ml/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Train failed (${response.status}): ${text}`);
  }
  return response.json() as Promise<MlTrainResult>;
}

export async function listMlModels(): Promise<{
  count: number;
  models: MlModelSummary[];
}> {
  return apiGet("/api/ml/models");
}

export type CombinedSignalResponse = {
  signal_id?: string;
  setup_id?: string;
  symbol: string;
  as_of: string;
  direction: string;
  rule_signal: string;
  rule_score: number;
  ml_prediction?: string | null;
  ml_confidence?: number | null;
  ml_model_id?: string | null;
  ml_model_version?: string | null;
  ml_status: string;
  probability_calibrated: boolean;
  combined_score?: number | null;
  entry?: { low: number; high: number; preferred: number } | null;
  stop_loss?: number | null;
  targets: Array<{ price: number; rr: number; label: string }>;
  reasons: string[];
  risks: string[];
  rule_reasons: string[];
  ml_reasons: string[];
  notes: string[];
};

export type CombinedCompareResult = {
  split: string;
  model_id?: string | null;
  threshold_frozen_from_validation: number;
  RULE_ONLY: Record<string, number>;
  ML_FILTER: Record<string, number>;
  filter_quality: {
    trades_filtered: number;
    losers_avoided: number;
    winners_rejected: number;
    filter_efficiency?: number | null;
  };
  delta: Record<string, number>;
};

export async function fetchCombinedAnalyze(options?: {
  symbol?: string;
  model_id?: string;
  mode?: string;
  as_of?: string;
}): Promise<CombinedSignalResponse> {
  const params = new URLSearchParams();
  if (options?.symbol) params.set("symbol", options.symbol);
  if (options?.model_id) params.set("model_id", options.model_id);
  if (options?.mode) params.set("mode", options.mode);
  if (options?.as_of) params.set("as_of", options.as_of);
  const q = params.toString();
  return apiGet(`/api/combined/analyze${q ? `?${q}` : ""}`);
}

export async function compareRuleVsMl(body: {
  symbol?: string;
  model_id?: string;
  min_ml_confidence?: number;
  run_threshold_scan?: boolean;
  evaluate_test?: boolean;
  limit?: number;
}): Promise<CombinedCompareResult> {
  const response = await fetch(`${API_BASE}/api/combined/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Compare failed (${response.status}): ${text}`);
  }
  return response.json() as Promise<CombinedCompareResult>;
}

/* ——— Phase 11 Risk ——— */

export type TradePlan = {
  instrument: string;
  direction: string;
  signal_status: string;
  rule_score?: number | null;
  ml_prediction?: string | null;
  ml_confidence?: number | null;
  entry?: number | null;
  stop_loss?: number | null;
  targets: Array<{ price: number; rr?: number; label: string }>;
  account_balance: number;
  currency: string;
  risk_percent: number;
  risk_amount: number;
  quantity: number;
  notional_value: number;
  leverage: number;
  required_margin: number;
  estimated_total_cost: number;
  gross_rr?: number | null;
  net_rr?: number | null;
  risk_status: string;
  reasons: string[];
  risks: string[];
  notes: string[];
};

export type RiskAnalyzeResponse = {
  trade_plan: TradePlan;
  label: string;
};

export type RiskConfigResponse = {
  account: Record<string, unknown> & {
    account_balance: number;
    risk_per_trade_pct: number;
    default_leverage: number;
    minimum_rr: number;
    max_total_exposure_pct: number;
    max_daily_loss_pct: number;
    max_consecutive_losses: number;
  };
  default_instrument: string;
  instruments: unknown[];
  notes: string[];
};

export async function fetchRiskAnalyze(options?: {
  symbol?: string;
  account_balance?: number;
  risk_percent?: number;
  leverage?: number;
  minimum_rr?: number;
  mode?: string;
}): Promise<RiskAnalyzeResponse> {
  const params = new URLSearchParams();
  if (options?.symbol) params.set("symbol", options.symbol);
  if (options?.account_balance != null)
    params.set("account_balance", String(options.account_balance));
  if (options?.risk_percent != null)
    params.set("risk_percent", String(options.risk_percent));
  if (options?.leverage != null) params.set("leverage", String(options.leverage));
  if (options?.minimum_rr != null)
    params.set("minimum_rr", String(options.minimum_rr));
  if (options?.mode) params.set("mode", options.mode);
  const q = params.toString();
  return apiGet(`/api/risk/analyze${q ? `?${q}` : ""}`);
}

export async function fetchRiskConfig(): Promise<RiskConfigResponse> {
  return apiGet("/api/risk/config");
}

export async function putRiskConfig(
  account: Record<string, unknown>,
): Promise<{ account: RiskConfigResponse["account"]; status: string }> {
  const response = await fetch(`${API_BASE}/api/risk/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(account),
  });
  if (!response.ok) {
    throw new Error(`Risk config update failed (${response.status})`);
  }
  return response.json();
}

export async function runRiskBacktest(body: {
  symbol?: string;
  risk_mode?: string;
  risk_fraction_per_trade?: number;
  initial_equity?: number;
  limit?: number;
  signal_mode?: string;
}): Promise<{
  backtest: { metrics?: Record<string, number | string | null> };
  loss_streaks: { max_consecutive_losses: number };
  ruin_estimate: { rough_ruin_hint: string };
  notes: string[];
}> {
  const response = await fetch(`${API_BASE}/api/risk/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Risk backtest failed (${response.status}): ${text}`);
  }
  return response.json();
}
