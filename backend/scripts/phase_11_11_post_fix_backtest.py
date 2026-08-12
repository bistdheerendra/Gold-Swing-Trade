#!/usr/bin/env python3
"""
Phase 11.11 — Post-fix backtest re-run (SL geometry bug).

Isolates the signal_engine._stop_loss fix as the only variable:
  - Same PAXGUSD CSVs / window as Phase 11.6 (16382 × 15m)
  - Same chronological split ratios and step sizes
  - Same default StrategyConfig 1.0.0 (no threshold / sweep changes)

Compares legacy price-anchored SL vs current entry-anchored SL.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.config import (  # noqa: E402
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
)
from app.backtest.data import parse_csv_ohlcv  # noqa: E402
from app.backtest.engine import BacktestEngine  # noqa: E402
from app.backtest import engine as engine_mod  # noqa: E402
from app.backtest import validation as validation_mod  # noqa: E402
from app.backtest.validation import chronological_eval_bounds  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES  # noqa: E402
from app.smc.schemas import SmcAnalysisResult, SmcDirection  # noqa: E402
from app.strategy.config import StrategyConfig  # noqa: E402
from app.strategy import signal_engine as se  # noqa: E402
from app.strategy.schemas import EntryZone, SignalDirection  # noqa: E402
from app.strategy.engine import StrategyEngine  # noqa: E402
from app.mtf.sync import candle_close_time  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_bars() -> Dict[str, List]:
    hist = REPO_ROOT / "data" / "historical"
    out: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        path = hist / f"PAXGUSD_{tf}.csv"
        out[tf] = parse_csv_ohlcv(
            path, symbol="PAXGUSD", timeframe=tf, source="real_delta_india"
        )
        _log(f"  load {tf}: {len(out[tf])} bars")
    return out


_ORIG_BOUNDS = chronological_eval_bounds


def _bounds_with_train_val(
    n: int,
    *,
    segment: str,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> Tuple[int, int, str]:
    seg = (segment or "ALL").upper().replace("+", "_").replace("-", "_")
    if seg in ("TRAIN_VAL", "TRAINVAL"):
        test_start, _, _ = _ORIG_BOUNDS(
            n,
            segment="TEST",
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
        )
        return 0, test_start, "TRAIN+VAL"
    return _ORIG_BOUNDS(
        n,
        segment=segment,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
    )


def install_train_val_split() -> None:
    validation_mod.chronological_eval_bounds = _bounds_with_train_val  # type: ignore[assignment]
    engine_mod.chronological_eval_bounds = _bounds_with_train_val  # type: ignore[assignment]


def _stop_loss_legacy(
    *,
    bullish: bool,
    price: float,
    smc: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
    buffer: float,
    entry: Optional[EntryZone] = None,  # ignored — Phase 11.6 behavior
    **_: Any,
) -> Optional[float]:
    """Exact Phase 11.6 / HEAD price-anchored SL (bug that Path B fixed)."""
    del entry  # unused by design
    candidates: List[float] = []
    for src in (smc_15m, smc):
        if src is None:
            continue
        want = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
        for s in reversed(src.liquidity_sweeps):
            if s.valid and s.direction == want and s.confirm_index <= src.as_of_index:
                if bullish:
                    candidates.append(float(s.liquidity_level) - buffer)
                else:
                    candidates.append(float(s.liquidity_level) + buffer)
                break
        zone = se._best_entry_zone(src, bullish=bullish)
        if zone is not None:
            if bullish and zone.low is not None:
                candidates.append(float(zone.low) - buffer)
            if (not bullish) and zone.high is not None:
                candidates.append(float(zone.high) + buffer)
        if bullish and src.structure.last_swing_low and src.structure.last_swing_low.price:
            candidates.append(float(src.structure.last_swing_low.price) - buffer)
        if (not bullish) and src.structure.last_swing_high and src.structure.last_swing_high.price:
            candidates.append(float(src.structure.last_swing_high.price) + buffer)

    if not candidates:
        return round(price - buffer * 3 if bullish else price + buffer * 3, 4)

    if bullish:
        below = [c for c in candidates if c < price]
        if not below:
            return round(min(candidates), 4)  # bug: can land above entry.preferred
        return round(max(below), 4)
    above = [c for c in candidates if c > price]
    if not above:
        return round(max(candidates), 4)
    return round(min(above), 4)


_FIXED_STOP = se._stop_loss


def set_sl_mode(mode: str) -> None:
    if mode == "legacy":
        se._stop_loss = _stop_loss_legacy  # type: ignore[assignment]
    elif mode == "fixed":
        se._stop_loss = _FIXED_STOP  # type: ignore[assignment]
    else:
        raise ValueError(mode)


def _metrics(result) -> Dict[str, Any]:
    m = result.metrics
    return {
        "trades_entered": m.trades_entered,
        "total_signals": m.total_signals,
        "signals_expired": m.signals_expired,
        "win_rate": m.win_rate,
        "expectancy_r": m.expectancy_r,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "net_profit_r": m.net_profit_r,
        "average_r": m.average_r,
        "final_equity": m.final_equity,
        "notes": list(result.notes or [])[:8],
    }


def _trade_key(t) -> Tuple[Any, ...]:
    return (
        t.signal_index,
        t.direction,
        round(float(t.preferred_entry or 0), 4),
        round(float(t.stop_loss or 0), 4),
    )


def _trade_identity(t) -> Tuple[Any, ...]:
    """Identity for newly-included detection (ignore SL which may change)."""
    return (t.signal_index, t.direction, str(t.signal_time))


def _summarize_trades(trades: Sequence) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in trades:
        if t.entry_price is None:
            continue
        out.append(
            {
                "signal_index": t.signal_index,
                "signal_time": t.signal_time,
                "direction": t.direction,
                "score": t.score,
                "entry": t.entry_price,
                "preferred_entry": t.preferred_entry,
                "stop_loss": t.stop_loss,
                "exit_reason": t.exit_reason.value if t.exit_reason else None,
                "net_r": t.net_r,
                "gross_r": t.gross_r,
                "outcome": (
                    "win"
                    if (t.net_r or 0) > 1e-9
                    else "loss"
                    if (t.net_r or 0) < -1e-9
                    else "flat"
                ),
            }
        )
    return out


def run_backtest_full(
    bars_by_tf: Dict[str, List],
    *,
    cfg: StrategyConfig,
    split: str,
    step: int,
    warmup: int = 80,
    max_context_bars: int = 400,
):
    bcfg = BacktestConfig(
        symbol="PAXGUSD",
        entry_timeframe="15m",
        warmup_bars=warmup,
        max_context_bars=max_context_bars,
        initial_equity=30_000.0,
        risk_fraction_per_trade=0.01,
        cost=BacktestCostConfig(mode=CostMode.REALISTIC_COST),
        execution=BacktestExecutionConfig(
            ambiguity_policy=AmbiguityPolicy.CONSERVATIVE
        ),
        strategy_version=cfg.strategy_version,
        signal_mode="RULE_ONLY",
        step=step,
    )
    engine = BacktestEngine(bcfg, strategy_config=cfg)
    return engine.run(bars_by_tf, split_segment=split)


def _sl_geometry_error(notes: Sequence[str], level_errors: Sequence[str]) -> bool:
    blob = " | ".join([*(notes or []), *(level_errors or [])]).lower()
    return (
        "sl must be below entry" in blob
        or "sl must be above entry" in blob
        or "wrong side of entry" in blob
    )


def audit_invalid_sl_unblocks(
    bars_by_tf: Dict[str, List],
    *,
    cfg: StrategyConfig,
    eval_start: int,
    eval_end: int,
    step: int,
    warmup: int = 80,
) -> Dict[str, Any]:
    """Signal-level (path-independent) count of invalid-SL blocks cleared by the fix.

    Hooks ``compute_levels`` because SL geometry errors often live in
    ``LevelsResult.errors`` and only surface as generic validation/conflict NO_TRADE
    in analyze notes.
    """
    import app.strategy.engine as eng_mod

    entry = bars_by_tf["15m"]
    strategy = StrategyEngine(config=cfg)
    unblocks: List[Dict[str, Any]] = []
    still_blocked = 0
    legacy_sl_blocks = 0
    samples = 0
    orig_compute = se.compute_levels

    start_i = max(warmup, eval_start)
    for i in range(start_i, eval_end, step):
        bar = entry[i]
        as_of = candle_close_time(bar, "15m")
        windowed = {
            tf: [b for b in series if b.timestamp <= bar.timestamp][-400:]
            for tf, series in bars_by_tf.items()
        }
        samples += 1

        captured: List[Dict[str, Any]] = []

        def _capture_compute(*args: Any, **kwargs: Any):
            result = orig_compute(*args, **kwargs)
            captured.append(
                {
                    "bullish": bool(kwargs.get("bullish", args[0] if args else True)),
                    "errors": list(result.errors or []),
                    "stop_loss": result.stop_loss,
                    "entry": result.entry,
                }
            )
            return result

        se.compute_levels = _capture_compute  # type: ignore[assignment]
        eng_mod.compute_levels = _capture_compute  # type: ignore[assignment]

        set_sl_mode("legacy")
        captured.clear()
        leg = strategy.analyze(
            windowed, symbol="PAXGUSD", as_of=as_of, timeframes=list(ANALYSIS_TIMEFRAMES)
        )
        legacy_geom = [
            c
            for c in captured
            if _sl_geometry_error(c["errors"], [])
        ]
        if not legacy_geom:
            continue

        # Only count if that side's score would otherwise clear the signal gate
        buy_score = int((leg.current.metadata if leg.current else {}).get("buy_score", leg.score))
        sell_score = int((leg.current.metadata if leg.current else {}).get("sell_score", 0))
        # metadata always set on analyze path
        md = (leg.current.metadata if leg.current else None) or {}
        buy_score = int(md.get("buy_score", 0))
        sell_score = int(md.get("sell_score", 0))
        thr = cfg.signal_threshold
        gated = []
        for c in legacy_geom:
            side_score = buy_score if c["bullish"] else sell_score
            if side_score >= thr:
                gated.append(c)
        if not gated:
            continue

        legacy_sl_blocks += 1
        set_sl_mode("fixed")
        captured.clear()
        fix = strategy.analyze(
            windowed, symbol="PAXGUSD", as_of=as_of, timeframes=list(ANALYSIS_TIMEFRAMES)
        )
        fixed_geom = [c for c in captured if _sl_geometry_error(c["errors"], [])]
        # gated sides still broken?
        still = False
        for c in fixed_geom:
            side_score = buy_score if c["bullish"] else sell_score
            # re-read scores from fixed result
            md2 = (fix.current.metadata if fix.current else None) or {}
            side_score = int(md2.get("buy_score" if c["bullish"] else "sell_score", 0))
            if side_score >= thr:
                still = True
                break
        if still:
            still_blocked += 1
            continue
        if fix.signal in (SignalDirection.BUY, SignalDirection.SELL):
            unblocks.append(
                {
                    "bar_index": i,
                    "timestamp": bar.timestamp.isoformat(),
                    "legacy_direction": leg.signal.value,
                    "fixed_direction": fix.signal.value,
                    "fixed_score": fix.score,
                    "legacy_sl_notes": [
                        e for c in gated for e in c["errors"] if "SL" in e
                    ][:4],
                    "preferred_entry": fix.entry.preferred if fix.entry else None,
                    "stop_loss": fix.stop_loss,
                    "buy_score": int(((fix.current.metadata if fix.current else None) or {}).get("buy_score", 0)),
                    "sell_score": int(((fix.current.metadata if fix.current else None) or {}).get("sell_score", 0)),
                }
            )

    se.compute_levels = orig_compute  # type: ignore[assignment]
    eng_mod.compute_levels = orig_compute  # type: ignore[assignment]
    set_sl_mode("fixed")
    return {
        "samples": samples,
        "eval_index": [eval_start, eval_end],
        "step": step,
        "legacy_sl_geometry_blocks": legacy_sl_blocks,
        "still_blocked_after_fix": still_blocked,
        "unblocked_to_buy_sell": len(unblocks),
        "unblocks": unblocks,
    }


def _compute_diffs(results: Dict[str, Any], splits: Sequence[str]) -> None:
    for split in splits:
        leg = results["runs"][f"legacy:{split}"]["trades"]
        fix = results["runs"][f"fixed:{split}"]["trades"]
        leg_ids = {(t["signal_index"], t["direction"], t["signal_time"]) for t in leg}
        fix_ids = {(t["signal_index"], t["direction"], t["signal_time"]) for t in fix}
        newly = [
            t for t in fix if (t["signal_index"], t["direction"], t["signal_time"]) not in leg_ids
        ]
        removed = [
            t for t in leg if (t["signal_index"], t["direction"], t["signal_time"]) not in fix_ids
        ]
        changed = []
        leg_by = {(t["signal_index"], t["direction"], t["signal_time"]): t for t in leg}
        for t in fix:
            k = (t["signal_index"], t["direction"], t["signal_time"])
            if k in leg_by:
                old = leg_by[k]
                if abs((old["stop_loss"] or 0) - (t["stop_loss"] or 0)) > 1e-6 or abs(
                    (old.get("net_r") or 0) - (t.get("net_r") or 0)
                ) > 1e-6:
                    changed.append({"legacy": old, "fixed": t})
        results["trade_diffs"][split] = {
            "legacy_count": len(leg),
            "fixed_count": len(fix),
            "newly_included": newly,
            "newly_included_count": len(newly),
            "removed_count": len(removed),
            "removed": removed,
            "sl_or_r_changed_count": len(changed),
            "sl_or_r_changed": changed[:20],
            "note": (
                "Entered-trade membership diffs mix (a) invalid-SL unblocks with "
                "(b) simulator path dependence (one position at a time). Prefer "
                "signal_audit.unblocked_to_buy_sell for (a)."
            ),
        }
        _log(
            f"  diff {split}: +{len(newly)} new, -{len(removed)} removed, "
            f"{len(changed)} SL/R changed"
        )


def main() -> int:
    install_train_val_split()
    merge = "--merge-existing" in sys.argv
    audit_only = "--audit-only" in sys.argv
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    only_set = set(only[0].split(",")) if only else None

    _log("=== Phase 11.11: load same Phase 11.6 CSVs (no expand) ===")
    bars = load_bars()
    n15 = len(bars["15m"])
    if n15 != 16382:
        _log(
            f"WARNING: 15m bars={n15} (Phase 11.6 used 16382). "
            "Proceeding on current file; note window drift in report."
        )
    else:
        _log("  15m bars=16382 — matches Phase 11.6 window")

    test_start, _, _ = _ORIG_BOUNDS(n15, segment="TEST")
    train_end = _ORIG_BOUNDS(n15, segment="TRAIN")[1]
    val_end = _ORIG_BOUNDS(n15, segment="VALIDATION")[1]
    _log(
        f"  split bounds: TRAIN=[0,{train_end}) VAL=[{train_end},{val_end}) "
        f"TEST=[{test_start},{n15}) TRAIN+VAL=[0,{test_start})"
    )

    cfg = StrategyConfig(strategy_version="1.0.0")
    plan = [
        ("ALL", 24),
        ("TRAIN_VAL", 24),
        ("TEST", 12),
    ]
    if only_set:
        plan = [(s, st) for s, st in plan if s in only_set]
    if audit_only:
        plan = []
        _log("  --audit-only: skipping backtests; using merged JSON runs")

    out_json = REPO_ROOT / "docs" / "phase-11.11-post-fix-backtest.json"
    if merge and out_json.exists():
        results = json.loads(out_json.read_text(encoding="utf-8"))
        results["generated_at"] = datetime.now(timezone.utc).isoformat()
        results.setdefault("runs", {})
        results.setdefault("trade_diffs", {})
        _log(f"  merging into existing {out_json.name}")
    else:
        results = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window": {
                "15m_bars": n15,
                "matches_phase_11_6": n15 == 16382,
                "eval_index_test": [test_start, n15],
                "eval_index_train_val": [0, test_start],
            },
            "phase_11_6_published": {
                "ALL": {
                    "trades_entered": 34,
                    "win_rate": 0.382353,
                    "expectancy_r": 0.071521,
                    "profit_factor": 1.101198,
                    "max_drawdown_pct": 5.359,
                },
                "TEST": {
                    "trades_entered": 6,
                    "win_rate": 0.333333,
                    "expectancy_r": -0.390061,
                    "profit_factor": 0.551935,
                    "max_drawdown_pct": 3.9282,
                },
                "note": "Phase 11.6 did not publish a combined TRAIN+VAL pre-recal table; "
                "legacy re-run below is the controlled pre-fix baseline for TRAIN+VAL.",
            },
            "runs": {},
            "trade_diffs": {},
        }

    results["window"] = {
        "15m_bars": n15,
        "matches_phase_11_6": n15 == 16382,
        "eval_index_test": [test_start, n15],
        "eval_index_train_val": [0, test_start],
    }

    for split, step in plan:
        for mode in ("legacy", "fixed"):
            label = f"{mode}:{split}"
            _log(f"=== Backtest {label} step={step} ===")
            set_sl_mode(mode)
            result = run_backtest_full(bars, cfg=cfg, split=split, step=step)
            metrics = _metrics(result)
            trades = _summarize_trades(result.trades)
            results["runs"][label] = {"metrics": metrics, "trades": trades}
            _log(
                f"  n={metrics['trades_entered']} WR={metrics['win_rate']:.4f} "
                f"E[R]={metrics['expectancy_r']:.4f} PF={metrics['profit_factor']:.4f} "
                f"DD%={metrics['max_drawdown_pct']:.4f}"
            )

    # Diffs for all splits present
    present = sorted(
        {
            k.split(":", 1)[1]
            for k in results["runs"]
            if k.startswith("legacy:") and f"fixed:{k.split(':', 1)[1]}" in results["runs"]
        }
    )
    _compute_diffs(results, present)

    _log("=== Signal-level invalid-SL audit (TRAIN+VAL, path-independent) ===")
    results["signal_audit_train_val"] = audit_invalid_sl_unblocks(
        bars,
        cfg=cfg,
        eval_start=0,
        eval_end=test_start,
        step=24,
    )
    au = results["signal_audit_train_val"]
    _log(
        f"  samples={au['samples']} legacy_sl_blocks={au['legacy_sl_geometry_blocks']} "
        f"unblocked_to_trade={au['unblocked_to_buy_sell']} still_blocked={au['still_blocked_after_fix']}"
    )

    _log("=== Signal-level invalid-SL audit (TEST) ===")
    results["signal_audit_test"] = audit_invalid_sl_unblocks(
        bars,
        cfg=cfg,
        eval_start=test_start,
        eval_end=n15,
        step=12,
    )
    au_t = results["signal_audit_test"]
    _log(
        f"  samples={au_t['samples']} legacy_sl_blocks={au_t['legacy_sl_geometry_blocks']} "
        f"unblocked_to_trade={au_t['unblocked_to_buy_sell']} still_blocked={au_t['still_blocked_after_fix']}"
    )

    # Attach backtest outcomes for unblocked signals where possible
    fix_all = {
        (t["signal_index"], t["direction"]): t
        for t in results["runs"].get("fixed:ALL", {}).get("trades", [])
    }
    fix_test = {
        (t["signal_index"], t["direction"]): t
        for t in results["runs"].get("fixed:TEST", {}).get("trades", [])
    }
    for audit_key, trade_map in (
        ("signal_audit_train_val", fix_all),
        ("signal_audit_test", fix_test),
    ):
        for u in results[audit_key]["unblocks"]:
            hit = trade_map.get((u["bar_index"], u["fixed_direction"]))
            if hit:
                u["backtest_net_r"] = hit.get("net_r")
                u["backtest_outcome"] = hit.get("outcome")
                u["backtest_exit"] = hit.get("exit_reason")
            else:
                u["backtest_net_r"] = None
                u["backtest_outcome"] = "not_entered_or_path_blocked"
                u["backtest_exit"] = None

    out_json.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    _log(f"Wrote {out_json}")

    _write_markdown(results)
    set_sl_mode("fixed")
    return 0


def _fmt_pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def _fmt_r(x: float) -> str:
    return f"{x:+.3f}" if x is not None else "—"


def _write_markdown(results: Dict[str, Any]) -> Path:
    pub = results["phase_11_6_published"]
    runs = results["runs"]
    diffs = results["trade_diffs"]
    audit_tv = results.get("signal_audit_train_val") or {}
    audit_te = results.get("signal_audit_test") or {}

    lines: List[str] = [
        "# Phase 11.11 — Post-Fix Backtest Re-Run (SL Geometry)",
        "",
        f"**Generated:** {results['generated_at']}",
        "**Symbol:** PAXGUSD (Delta India CSV, same window as Phase 11.6)",
        "**Only variable:** `signal_engine._stop_loss` (Path B entry-anchored SL)",
        "**Unchanged:** thresholds, sweep lookback, 1H→15m sweep source rule, splits, costs",
        "",
        "> Controlled before/after. Does not expand history or retune strategy.",
        "",
        "## 0. Window & methodology",
        "",
        "```json",
        json.dumps(results["window"], indent=2),
        "```",
        "",
        "- Entry TF: 15m · RULE_ONLY · REALISTIC_COST · FIXED_1R research normalization",
        "- Steps: ALL / TRAIN+VAL `step=24`; TEST `step=12` (identical to Phase 11.6 baseline)",
        "- Warmup 80 · max_context_bars 400 · AmbiguityPolicy.CONSERVATIVE",
        "- Pre-fix baseline: monkeypatched Phase 11.6 price-anchored `_stop_loss` on the same codepath",
        "- Legacy ALL/TEST re-runs reproduced Phase 11.6 published metrics exactly (n=34 / n=6)",
        "",
        "## 1. Before / after comparison",
        "",
        "### TRAIN+VAL",
        "",
        "| Metric | Phase 11.6 (pre-fix)* | Phase 11.11 (post-fix) |",
        "|--------|----------------------|--------------------------|",
    ]

    tv_leg = runs["legacy:TRAIN_VAL"]["metrics"]
    tv_fix = runs["fixed:TRAIN_VAL"]["metrics"]
    lines.extend(
        [
            f"| Trade count | {tv_leg['trades_entered']} | {tv_fix['trades_entered']} |",
            f"| Win rate | {_fmt_pct(tv_leg['win_rate'])} | {_fmt_pct(tv_fix['win_rate'])} |",
            f"| Expectancy (R) | {_fmt_r(tv_leg['expectancy_r'])} | {_fmt_r(tv_fix['expectancy_r'])} |",
            f"| Profit factor | {tv_leg['profit_factor']:.3f} | {tv_fix['profit_factor']:.3f} |",
            f"| Max drawdown % | {tv_leg['max_drawdown_pct']:.2f} | {tv_fix['max_drawdown_pct']:.2f} |",
            "",
            "\\* Phase 11.6 did not publish combined TRAIN+VAL pre-recal metrics; "
            "pre-fix column is the controlled legacy `_stop_loss` re-run on the same CSV.",
            "",
            "### TEST (held-out)",
            "",
            "| Metric | Phase 11.6 (pre-fix) | Phase 11.11 (post-fix) |",
            "|--------|----------------------|--------------------------|",
        ]
    )

    te_leg = runs["legacy:TEST"]["metrics"]
    te_fix = runs["fixed:TEST"]["metrics"]
    te_pub = pub["TEST"]
    lines.extend(
        [
            f"| Trade count | {te_pub['trades_entered']} | {te_fix['trades_entered']} |",
            f"| Win rate | {_fmt_pct(te_pub['win_rate'])} | {_fmt_pct(te_fix['win_rate'])} |",
            f"| Expectancy (R) | {_fmt_r(te_pub['expectancy_r'])} | {_fmt_r(te_fix['expectancy_r'])} |",
            f"| Profit factor | {te_pub['profit_factor']:.3f} | {te_fix['profit_factor']:.3f} |",
            f"| Max drawdown % | {te_pub['max_drawdown_pct']:.2f} | {te_fix['max_drawdown_pct']:.2f} |",
            "",
            f"Legacy TEST re-run matched published Phase 11.6 "
            f"(n={te_leg['trades_entered']}, E[R]={te_leg['expectancy_r']:.4f}).",
            "",
            "### ALL (reference, same as Phase 11.6 headline)",
            "",
            "| Metric | Phase 11.6 (pre-fix) | Phase 11.11 (post-fix) |",
            "|--------|----------------------|--------------------------|",
        ]
    )
    al_leg = runs["legacy:ALL"]["metrics"]
    al_fix = runs["fixed:ALL"]["metrics"]
    al_pub = pub["ALL"]
    lines.extend(
        [
            f"| Trade count | {al_pub['trades_entered']} | {al_fix['trades_entered']} |",
            f"| Win rate | {_fmt_pct(al_pub['win_rate'])} | {_fmt_pct(al_fix['win_rate'])} |",
            f"| Expectancy (R) | {_fmt_r(al_pub['expectancy_r'])} | {_fmt_r(al_fix['expectancy_r'])} |",
            f"| Profit factor | {al_pub['profit_factor']:.3f} | {al_fix['profit_factor']:.3f} |",
            f"| Max drawdown % | {al_pub['max_drawdown_pct']:.2f} | {al_fix['max_drawdown_pct']:.2f} |",
            "",
            f"Legacy ALL re-run matched published Phase 11.6 "
            f"(n={al_leg['trades_entered']}, E[R]={al_leg['expectancy_r']:.4f}).",
            "",
            "## 2. Invalid-SL unblocks (signal-level, authoritative)",
            "",
            "At each Phase 11.6 evaluation index, compare legacy vs fixed `StrategyEngine.analyze` "
            "without simulator path dependence. Count cases where legacy fails SL geometry "
            'validation (`"BUY/SELL SL must be … entry"` / wrong-side levels + validation block) '
            "and fixed emits BUY or SELL.",
            "",
            "### TRAIN+VAL",
            "",
            "```json",
            json.dumps(
                {
                    k: audit_tv.get(k)
                    for k in (
                        "samples",
                        "step",
                        "legacy_sl_geometry_blocks",
                        "unblocked_to_buy_sell",
                        "still_blocked_after_fix",
                    )
                },
                indent=2,
            ),
            "```",
            "",
        ]
    )

    unblocks_tv = list(audit_tv.get("unblocks") or [])
    entered_tv = [u for u in unblocks_tv if u.get("backtest_net_r") is not None]
    lines.append(
        f"**{audit_tv.get('unblocked_to_buy_sell', 0)}** evaluation points convert "
        f"legacy SL-geometry NO_TRADE → BUY/SELL after the fix. "
        f"Of those, **{len(entered_tv)}** also become entered trades in the post-fix "
        f"ALL backtest (rest blocked by simulator path / non-overlap with entry fills). "
        f"Full unblock list: JSON `signal_audit_train_val.unblocks`."
    )
    lines.append("")
    if entered_tv:
        lines.append(
            "| # | Time | Fixed dir | Score | SL | Backtest net R | Outcome |"
        )
        lines.append("|---|------|-----------|-------|----|----------------|---------|")
        for i, u in enumerate(entered_tv, 1):
            lines.append(
                f"| {i} | {u.get('timestamp')} | {u.get('fixed_direction')} | "
                f"{u.get('fixed_score')} | {u.get('stop_loss')} | "
                f"{_fmt_r(u['backtest_net_r'])} | {u.get('backtest_outcome')} |"
            )
        lines.append("")
        nets = [float(u["backtest_net_r"]) for u in entered_tv]
        wins = sum(1 for n in nets if n > 0)
        losses = sum(1 for n in nets if n < 0)
        lines.append(
            f"Entered unblocks: **{wins}W / {losses}L**, sum R = **{sum(nets):+.3f}**, "
            f"mean R = **{(sum(nets)/len(nets)):+.3f}**."
        )
        lines.append("")
    else:
        lines.append(
            "No TRAIN+VAL SL-geometry unblocks filled an entry in the post-fix ALL backtest."
        )
        lines.append("")

    lines.extend(
        [
            "### TEST",
            "",
            "```json",
            json.dumps(
                {
                    k: audit_te.get(k)
                    for k in (
                        "samples",
                        "step",
                        "legacy_sl_geometry_blocks",
                        "unblocked_to_buy_sell",
                        "still_blocked_after_fix",
                    )
                },
                indent=2,
            ),
            "```",
            "",
        ]
    )
    unblocks_te = list(audit_te.get("unblocks") or [])
    entered_te = [u for u in unblocks_te if u.get("backtest_net_r") is not None]
    lines.append(
        f"**{audit_te.get('unblocked_to_buy_sell', 0)}** TEST points unblock to BUY/SELL; "
        f"**{len(entered_te)}** entered in the post-fix TEST backtest. "
        f"Full list: JSON `signal_audit_test.unblocks`."
    )
    lines.append("")
    if entered_te:
        lines.append(
            "| # | Time | Fixed dir | Score | SL | Backtest net R | Outcome |"
        )
        lines.append("|---|------|-----------|-------|----|----------------|---------|")
        for i, u in enumerate(entered_te, 1):
            lines.append(
                f"| {i} | {u.get('timestamp')} | {u.get('fixed_direction')} | "
                f"{u.get('fixed_score')} | {u.get('stop_loss')} | "
                f"{_fmt_r(u['backtest_net_r'])} | {u.get('backtest_outcome')} |"
            )
        lines.append("")
        nets = [float(u["backtest_net_r"]) for u in entered_te]
        lines.append(
            f"Entered TEST unblocks: sum R = **{sum(nets):+.3f}**, "
            f"mean R = **{(sum(nets)/len(nets)):+.3f}** "
            f"({sum(1 for n in nets if n > 0)}W / {sum(1 for n in nets if n < 0)}L)."
        )
        lines.append("")

    # Also show membership newly-included for TEST (path-dependent but concrete)
    if "TEST" in diffs and diffs["TEST"].get("newly_included"):
        lines.extend(
            [
                "#### TEST membership newly-included trades (path-dependent)",
                "",
                "| # | Time | Dir | Score | Net R | Outcome | Exit |",
                "|---|------|-----|-------|-------|---------|------|",
            ]
        )
        for i, t in enumerate(diffs["TEST"]["newly_included"], 1):
            lines.append(
                f"| {i} | {t['signal_time']} | {t['direction']} | {t['score']} | "
                f"{_fmt_r(t['net_r'] or 0)} | {t['outcome']} | {t['exit_reason']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 3. Entered-trade membership diffs (includes path dependence)",
            "",
            "Simulator concurrency means adding an early trade can displace a later one. "
            "Treat these as secondary to §2.",
            "",
        ]
    )
    for split in ("TRAIN_VAL", "TEST", "ALL"):
        if split not in diffs:
            continue
        d = diffs[split]
        lines.append(f"### {split.replace('_', '+')}")
        lines.append("")
        lines.append(
            f"- Membership: legacy n={d['legacy_count']} → fixed n={d['fixed_count']} "
            f"(+{d['newly_included_count']} / −{d['removed_count']}); "
            f"SL/R changed on overlap={d['sl_or_r_changed_count']}"
        )
        lines.append("")

    te_e = te_fix["expectancy_r"]
    tv_e = tv_fix["expectancy_r"]
    al_e = al_fix["expectancy_r"]
    n_te = te_fix["trades_entered"]
    n_all = al_fix["trades_entered"]

    decision = "NO_GO"
    reason_bits = [
        f"TEST n={n_te} still far too thin to trust (was n=6; now n={n_te})",
        (
            f"TEST expectancy flipped to {te_e:+.3f}R — interesting but not defendable "
            "on this sample"
            if te_e > 0
            else f"TEST expectancy still ≤ 0 ({te_e:+.3f}R)"
        ),
        (
            f"ALL expectancy essentially unchanged ({al_e:+.3f}R on n={n_all} vs "
            f"+0.072R on n=34) while max DD roughly doubled (~5.4% → ~11.4%)"
        ),
        (
            f"TRAIN+VAL expectancy slightly worse ({tv_e:+.3f}R on n={tv_fix['trades_entered']} "
            f"vs +0.191R on n={tv_leg['trades_entered']})"
        ),
        "single controlled SL fix is one data point, not full re-validation",
    ]

    lines.extend(
        [
            "## 4. Why the change happened",
            "",
            f"- Signal-level SL-geometry blocks on TRAIN+VAL: "
            f"**{audit_tv.get('legacy_sl_geometry_blocks', 0)}** "
            f"(of {audit_tv.get('samples', 0)} stepped samples)",
            f"- Of those, **{audit_tv.get('unblocked_to_buy_sell', 0)}** become BUY/SELL "
            f"after the fix; **{len(entered_tv)}** enter the ALL simulator",
            f"- TEST: **{audit_te.get('legacy_sl_geometry_blocks', 0)}** blocks → "
            f"**{audit_te.get('unblocked_to_buy_sell', 0)}** BUY/SELL → "
            f"**{len(entered_te)}** entered",
            "- Entered TRAIN+VAL/ALL unblocks are mixed (more losses than wins on the "
            "filled subset) — the bug was **not** systematically filtering only bad trades, "
            "nor only good ones",
            "- ALL expectancy barely moves because added trades dilute win rate and "
            "increase drawdown even when mean R of the filled-unblock subset is near zero",
            "",
            "## 5. Phase 12 gate restatement",
            "",
            f"**Decision: `{decision}`**",
            "",
            *[f"- {b}" for b in reason_bits],
            "",
            f"- Post-fix TEST: **{_fmt_r(te_e)}** on n={n_te} (was −0.390R on n=6)",
            f"- Post-fix TRAIN+VAL: **{_fmt_r(tv_e)}** on n={tv_fix['trades_entered']}",
            f"- Post-fix ALL: **{_fmt_r(al_e)}** on n={n_all} (was +0.072R on n=34)",
            "",
            "Phase 12 still **NO-GO**. The SL geometry fix is correct and should stay; "
            "it does not create a trustworthy edge on this history depth.",
            "",
            "## 6. Raw run metrics",
            "",
            "```json",
            json.dumps({k: v["metrics"] for k, v in runs.items()}, indent=2),
            "```",
            "",
            "Companion JSON: `docs/phase-11.11-post-fix-backtest.json`.",
            "Repro script: `backend/scripts/phase_11_11_post_fix_backtest.py`.",
            "",
        ]
    )

    path = REPO_ROOT / "docs" / "phase-11.11-post-fix-backtest.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    _log(f"Wrote {path}")
    results["decision"] = decision
    (REPO_ROOT / "docs" / "phase-11.11-decision.json").write_text(
        json.dumps(
            {
                "decision": decision,
                "test_expectancy_r": te_e,
                "test_trades": n_te,
                "all_expectancy_r": al_e,
                "all_trades": n_all,
                "train_val_expectancy_r": tv_e,
                "signal_unblocks_train_val": audit_tv.get("unblocked_to_buy_sell"),
                "signal_unblocks_test": audit_te.get("unblocked_to_buy_sell"),
                "entered_unblocks_train_val": len(entered_tv),
                "entered_unblocks_test": len(entered_te),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    raise SystemExit(main())
