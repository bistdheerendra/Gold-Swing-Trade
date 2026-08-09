"""Backtest schemas — trades, results, API payloads."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.backtest.config import BacktestConfig


class TradeLifecycle(str, Enum):
    SIGNAL = "SIGNAL"
    PENDING = "PENDING"
    ENTERED = "ENTERED"
    ACTIVE = "ACTIVE"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    AMBIGUOUS_SKIP = "AMBIGUOUS_SKIP"


class ExitReason(str, Enum):
    TP1 = "TP1"
    TP2 = "TP2"
    TP3 = "TP3"
    SL = "SL"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    AMBIGUOUS_SKIP = "AMBIGUOUS_SKIP"
    END_OF_DATA = "END_OF_DATA"


class BacktestTrade(BaseModel):
    trade_id: str
    signal_id: str
    setup_id: str
    symbol: str
    direction: str  # BUY | SELL
    status: TradeLifecycle
    signal_time: str
    signal_index: int
    entry_time: Optional[str] = None
    entry_index: Optional[int] = None
    entry_price: Optional[float] = None
    stop_loss: float
    targets: List[Dict[str, Any]] = Field(default_factory=list)
    selected_tp: Optional[float] = None
    exit_time: Optional[str] = None
    exit_index: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    gross_r: Optional[float] = None
    trading_cost_r: Optional[float] = None
    net_r: Optional[float] = None
    gross_pnl: Optional[float] = None
    trading_cost: Optional[float] = None
    net_pnl: Optional[float] = None
    duration_bars: Optional[int] = None
    score: int = 0
    strategy_version: str = "1.0.0"
    market_state: Optional[str] = None
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    preferred_entry: float = 0.0
    risk_points: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BacktestSignalRecord(BaseModel):
    signal_id: str
    setup_id: str
    timestamp: str
    bar_index: int
    direction: str
    score: int
    status: str
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    preferred_entry: Optional[float] = None
    stop_loss: Optional[float] = None
    market_state: Optional[str] = None


class EquityPoint(BaseModel):
    timestamp: str
    bar_index: int
    equity: float
    drawdown: float
    drawdown_pct: float
    peak: float


class PerformanceMetrics(BaseModel):
    total_signals: int = 0
    signals_expired: int = 0
    trades_entered: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: float = 0.0
    gross_profit_r: float = 0.0
    gross_loss_r: float = 0.0
    net_profit_r: float = 0.0
    average_win_r: float = 0.0
    average_loss_r: float = 0.0
    average_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_start: Optional[str] = None
    max_drawdown_end: Optional[str] = None
    longest_winning_streak: int = 0
    longest_losing_streak: int = 0
    average_trade_duration_bars: float = 0.0
    total_trading_cost: float = 0.0
    total_trading_cost_r: float = 0.0
    final_equity: float = 0.0
    initial_equity: float = 0.0


class BreakdownBucket(BaseModel):
    key: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    net_r: float = 0.0
    win_rate: float = 0.0


class BacktestResult(BaseModel):
    backtest_id: str
    symbol: str
    entry_timeframe: str
    start: str
    end: str
    strategy_version: str
    data_version: str
    config: BacktestConfig
    summary: Dict[str, Any] = Field(default_factory=dict)
    metrics: PerformanceMetrics
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    trades: List[BacktestTrade] = Field(default_factory=list)
    signals: List[BacktestSignalRecord] = Field(default_factory=list)
    breakdowns: Dict[str, List[BreakdownBucket]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BacktestRunRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "15m"
    start: Optional[str] = None
    end: Optional[str] = None
    initial_equity: float = 100_000.0
    cost_config: Optional[Dict[str, Any]] = None
    execution_config: Optional[Dict[str, Any]] = None
    split_segment: Optional[str] = None  # TRAIN | VALIDATION | TEST | ALL
    limit: int = Field(default=800, ge=100, le=20_000)
    source: str = "provider"  # provider | csv
    csv_path: Optional[str] = None
    warmup_bars: int = 80
    risk_fraction_per_trade: float = 0.01
    risk_mode: str = "FIXED_1R"  # FIXED_1R | RISK_PERCENT
    signal_mode: str = "RULE_ONLY"  # RULE_ONLY | ML_FILTER | COMBINED
    model_id: Optional[str] = None
    min_ml_confidence: Optional[float] = None
    step: int = 1
