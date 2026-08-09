"""RULE_ONLY vs ML_FILTER comparison + filter quality (Phase 10)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.backtest.schemas import BacktestResult, BacktestTrade
from app.ml.training_metrics import trading_metrics_from_r


def metrics_from_backtest(result: BacktestResult) -> Dict[str, Any]:
    m = result.metrics
    return {
        "trades": m.trades_entered,
        "win_rate": m.win_rate,
        "profit_factor": m.profit_factor,
        "expectancy_r": m.expectancy_r,
        "average_r": m.average_r,
        "net_r": m.net_profit_r,
        "max_drawdown_r": m.max_drawdown,  # equity units — also pct available
        "max_drawdown_pct": m.max_drawdown_pct,
        "average_win": m.average_win_r,
        "average_loss": m.average_loss_r,
        "longest_winning_streak": m.longest_winning_streak,
        "longest_losing_streak": m.longest_losing_streak,
    }


def filter_quality(
    rule_trades: Sequence[BacktestTrade],
    ml_trades: Sequence[BacktestTrade],
) -> Dict[str, Any]:
    """
    Compare rule-only closed trades vs ML-filtered trades by signal_id.
    Losers avoided / winners rejected among filtered-out rule trades.
    """
    ml_ids = {t.signal_id for t in ml_trades if t.net_r is not None}
    rule_closed = [t for t in rule_trades if t.net_r is not None]
    kept = [t for t in rule_closed if t.signal_id in ml_ids]
    rejected = [t for t in rule_closed if t.signal_id not in ml_ids]

    losers_avoided = sum(1 for t in rejected if (t.net_r or 0) < 0)
    winners_rejected = sum(1 for t in rejected if (t.net_r or 0) > 0)
    flat = sum(1 for t in rejected if (t.net_r or 0) == 0)

    return {
        "rule_trades": len(rule_closed),
        "ml_trades": len([t for t in ml_trades if t.net_r is not None]),
        "trades_filtered": len(rejected),
        "trades_kept": len(kept),
        "losers_avoided": losers_avoided,
        "winners_rejected": winners_rejected,
        "flat_filtered": flat,
        "filter_efficiency": round(
            losers_avoided / len(rejected), 6
        )
        if rejected
        else None,
        "rejected_net_r": round(sum(t.net_r or 0 for t in rejected), 6),
        "kept_net_r": round(sum(t.net_r or 0 for t in kept), 6),
    }


def comparison_report(
    rule_result: BacktestResult,
    ml_result: BacktestResult,
    *,
    threshold: float,
    model_id: Optional[str] = None,
    split: str = "TEST",
) -> Dict[str, Any]:
    fq = filter_quality(rule_result.trades, ml_result.trades)
    rule_m = metrics_from_backtest(rule_result)
    ml_m = metrics_from_backtest(ml_result)
    return {
        "label": "RESEARCH ONLY",
        "split": split,
        "model_id": model_id,
        "threshold_frozen_from_validation": threshold,
        "RULE_ONLY": rule_m,
        "ML_FILTER": ml_m,
        "filter_quality": fq,
        "delta": {
            "trades": (ml_m["trades"] or 0) - (rule_m["trades"] or 0),
            "expectancy_r": round(
                (ml_m["expectancy_r"] or 0) - (rule_m["expectancy_r"] or 0), 6
            ),
            "net_r": round((ml_m["net_r"] or 0) - (rule_m["net_r"] or 0), 6),
            "max_drawdown_pct": round(
                (ml_m["max_drawdown_pct"] or 0) - (rule_m["max_drawdown_pct"] or 0), 6
            ),
            "profit_factor": round(
                (ml_m["profit_factor"] or 0) - (rule_m["profit_factor"] or 0), 6
            ),
        },
        "notes": [
            "Threshold selected on VALIDATION only; TEST evaluated once.",
            "ML confidence is not guaranteed profit probability.",
        ],
    }
