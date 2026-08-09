"""Rule + ML filter research combination (not production Phase 10)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.training_metrics import trading_metrics_from_r


def combine_rule_ml(
    *,
    rule_directions: Sequence[Any],
    strategy_outcomes: Sequence[Any],
    future_rs: Sequence[Any],
    ml_proba: Optional[np.ndarray],
    classes: Sequence[str],
    accept_class: str = "WIN",
    threshold: float = 0.60,
) -> Dict[str, Any]:
    """
    Research-only: keep Phase 6 BUY/SELL trades when ML P(accept_class) >= threshold.
    Threshold must be chosen on validation, not test.
    """
    classes = list(classes)
    if ml_proba is None or accept_class not in classes:
        return {"error": "probability/accept_class unavailable"}

    idx = classes.index(accept_class)
    tags: List[str] = []
    filtered_r: List[float] = []
    rule_r: List[float] = []

    for i, direction in enumerate(rule_directions):
        d = str(direction).upper() if direction is not None else ""
        outcome = str(strategy_outcomes[i]) if strategy_outcomes[i] is not None else ""
        fr = future_rs[i]
        p = float(ml_proba[i, idx]) if i < len(ml_proba) else 0.0
        is_trade = outcome in ("WIN", "LOSS") or (
            d in ("BUY", "SELL", "1", "-1") and outcome not in ("NO_SETUP", "NO_ENTRY", "")
        )
        # Prefer explicit outcome WIN/LOSS rows for R
        if outcome in ("WIN", "LOSS") and fr is not None:
            try:
                rule_r.append(float(fr))
            except (TypeError, ValueError):
                pass
            if p >= threshold:
                try:
                    filtered_r.append(float(fr))
                except (TypeError, ValueError):
                    pass
                tags.append(f"RULE_{'BUY' if d in ('BUY', '1', 1) else 'SELL'}_ML_ACCEPT")
            else:
                tags.append(f"RULE_{'BUY' if d in ('BUY', '1', 1) else 'SELL'}_ML_REJECT")
        elif d in ("0", "WAIT", "NO_TRADE", ""):
            tags.append("WAIT" if d in ("0", "WAIT", "") else "NO_TRADE")
        else:
            tags.append("NO_TRADE")

    return {
        "threshold": threshold,
        "accept_class": accept_class,
        "rule_only": trading_metrics_from_r(rule_r),
        "rule_plus_ml": trading_metrics_from_r(filtered_r),
        "tag_counts": dict(
            sorted(
                {t: tags.count(t) for t in set(tags)}.items(),
                key=lambda x: -x[1],
            )
        ),
    }


def scan_thresholds_on_validation(
    *,
    rule_directions: Sequence[Any],
    strategy_outcomes: Sequence[Any],
    future_rs: Sequence[Any],
    ml_proba: np.ndarray,
    classes: Sequence[str],
    thresholds: Sequence[float] = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75),
    accept_class: str = "WIN",
) -> Dict[str, Any]:
    """Compare thresholds on VALIDATION only — never use TEST to pick."""
    results = []
    for thr in thresholds:
        res = combine_rule_ml(
            rule_directions=rule_directions,
            strategy_outcomes=strategy_outcomes,
            future_rs=future_rs,
            ml_proba=ml_proba,
            classes=classes,
            accept_class=accept_class,
            threshold=float(thr),
        )
        results.append(res)
    # select by validation expectancy then PF (research heuristic)
    valid = [r for r in results if r.get("rule_plus_ml", {}).get("trades", 0) > 0]
    if not valid:
        return {"selected_threshold": 0.60, "scan": results}
    best = max(
        valid,
        key=lambda r: (
            r["rule_plus_ml"].get("expectancy_r", -999),
            r["rule_plus_ml"].get("profit_factor", 0),
        ),
    )
    return {"selected_threshold": best["threshold"], "scan": results}
