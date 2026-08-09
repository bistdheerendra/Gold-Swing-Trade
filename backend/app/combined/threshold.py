"""Validation-only threshold scan for Phase 10 (never TEST)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.combined.comparison import filter_quality, metrics_from_backtest
from app.backtest.schemas import BacktestResult


DEFAULT_THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)


def select_threshold_on_validation(
    runs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    runs: list of {threshold, rule_result, ml_result}
    Select by validation expectancy then PF. Never include TEST runs here.
    """
    scored = []
    for r in runs:
        ml: BacktestResult = r["ml_result"]
        m = metrics_from_backtest(ml)
        scored.append(
            {
                "threshold": r["threshold"],
                "metrics": m,
                "filter_quality": filter_quality(r["rule_result"].trades, ml.trades),
            }
        )
    if not scored:
        return {"selected_threshold": 0.60, "scan": []}
    valid = [s for s in scored if (s["metrics"].get("trades") or 0) > 0]
    pool = valid or scored
    best = max(
        pool,
        key=lambda s: (
            s["metrics"].get("expectancy_r") or -999,
            s["metrics"].get("profit_factor") or 0,
        ),
    )
    return {
        "selected_threshold": best["threshold"],
        "scan": scored,
        "note": "Selected on VALIDATION only — freeze before TEST",
    }
