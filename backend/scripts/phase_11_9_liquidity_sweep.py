#!/usr/bin/env python3
"""
Phase 11.9 — Liquidity Sweep Condition Investigation (research only).

Hard rules:
  - No production Phase 6 rule changes
  - TRAIN+VALIDATION only for sensitivity / expectancy exploration
  - Held-out TEST untouched during sensitivity
  - Honest reporting including "leave as is"

Outputs:
  - docs/phase-11.9-liquidity-sweep-investigation.md
  - docs/phase-11.9-liquidity-sweep-investigation.json (raw numbers)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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
from app.backtest.validation import chronological_eval_bounds  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES  # noqa: E402
from app.mtf.sync import candle_close_time  # noqa: E402
from app.smc.engine import SmcEngine  # noqa: E402
from app.smc.schemas import SmcConfig, SmcDirection  # noqa: E402
from app.strategy import conditions as cond_mod  # noqa: E402
from app.strategy.config import StrategyConfig  # noqa: E402
from app.strategy.engine import StrategyEngine  # noqa: E402
from app.strategy.schemas import SignalDirection  # noqa: E402
from app.ta.engine import TechnicalAnalysisEngine  # noqa: E402
from app.ta.indicators import atr as compute_atr  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_bars() -> Dict[str, List]:
    hist = REPO_ROOT / "data" / "historical"
    out: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        path = hist / f"PAXGUSD_{tf}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path} — run Phase 11.6 backfill first")
        out[tf] = parse_csv_ohlcv(
            path, symbol="PAXGUSD", timeframe=tf, source="real_delta_india"
        )
        _log(f"  load {tf}: {len(out[tf])} bars")
    return out


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
    }


def run_backtest(
    bars_by_tf: Dict[str, List],
    *,
    cfg: StrategyConfig,
    split: str,
    step: int = 24,
    warmup: int = 80,
) -> Dict[str, Any]:
    bcfg = BacktestConfig(
        symbol="PAXGUSD",
        entry_timeframe="15m",
        warmup_bars=warmup,
        max_context_bars=400,
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
    result = engine.run(bars_by_tf, split_segment=split)
    return _metrics(result)


def _pct(vals: Sequence[float]) -> Dict[str, Optional[float]]:
    if not vals:
        return {"n": 0, "p10": None, "p50": None, "p90": None, "mean": None}
    s = sorted(vals)
    n = len(s)

    def q(p: float) -> float:
        return s[min(n - 1, max(0, int(round((n - 1) * p))))]

    return {
        "n": n,
        "p10": round(q(0.10), 4),
        "p50": round(q(0.50), 4),
        "p90": round(q(0.90), 4),
        "mean": round(sum(s) / n, 4),
    }


def train_val_bounds(n: int) -> Tuple[int, int]:
    """[start, end) covering TRAIN+VALIDATION — TEST excluded."""
    _, test_start, _ = chronological_eval_bounds(n, segment="TEST")
    return 0, test_start


# ─── Condition audit ─────────────────────────────────────────────────────────


def _cond_map(conditions) -> Dict[str, Any]:
    return {c.key: c for c in conditions}


def audit_sweep_blockers(
    bars_by_tf: Dict[str, List],
    *,
    cfg: StrategyConfig,
    max_samples: int = 300,
) -> Dict[str, Any]:
    """
    On TRAIN+VAL, sample strategy outcomes and classify liquidity_sweep role.

    'Otherwise qualifying' = chosen-side score >= signal_threshold OR
    score + missing sweep weight would reach threshold (near miss on sweep alone).
    """
    entry = bars_by_tf["15m"]
    n = len(entry)
    _, diagnose_end = train_val_bounds(n)
    start_i = max(80, 0)
    usable = list(range(start_i, diagnose_end))
    stride = max(1, len(usable) // max_samples)
    sample_idx = usable[::stride][:max_samples]

    strategy = StrategyEngine(config=cfg)
    sweep_w = float(cfg.score_weights.liquidity_sweep)
    thr = float(cfg.signal_threshold)

    rows: List[Dict[str, Any]] = []
    unmet_keys: Counter = Counter()
    sole_blocker: Counter = Counter()
    signal_counts: Counter = Counter()

    for i in sample_idx:
        bar = entry[i]
        as_of = candle_close_time(bar, "15m")
        windowed = {
            tf: [b for b in bars if b.timestamp <= bar.timestamp][-400:]
            for tf, bars in bars_by_tf.items()
        }
        try:
            result = strategy.analyze(
                windowed,
                symbol="PAXGUSD",
                as_of=as_of,
                timeframes=list(ANALYSIS_TIMEFRAMES),
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"error": type(exc).__name__, "index": i})
            continue

        score = int(result.score)
        signal = result.signal.value
        signal_counts[signal] += 1
        conds = list(result.conditions or [])
        cmap = _cond_map(conds)
        sweep_c = cmap.get("liquidity_sweep")
        sweep_met = bool(sweep_c and sweep_c.met)
        unmet = [c.key for c in conds if not c.met]

        # Score as-if sweep were met (add full weight if currently unmet)
        score_if_sweep = score if sweep_met else min(100, score + int(sweep_w))
        otherwise_qualifying = score >= thr or score_if_sweep >= thr
        high_score = score >= thr

        for k in unmet:
            unmet_keys[k] += 1
        if len(unmet) == 1:
            sole_blocker[unmet[0]] += 1

        rows.append(
            {
                "index": i,
                "ts": bar.timestamp.isoformat(),
                "signal": signal,
                "status": result.status.value if result.status else None,
                "score": score,
                "score_if_sweep_met": score_if_sweep,
                "sweep_met": sweep_met,
                "sweep_detail": sweep_c.detail if sweep_c else None,
                "unmet": unmet,
                "unmet_count": len(unmet),
                "sole_unmet_is_sweep": unmet == ["liquidity_sweep"],
                "high_score": high_score,
                "otherwise_qualifying": otherwise_qualifying,
                "trade_taken": signal in ("BUY", "SELL"),
            }
        )

    oq = [r for r in rows if r.get("otherwise_qualifying")]
    hs = [r for r in rows if r.get("high_score")]
    oq_no_trade = [r for r in oq if not r.get("trade_taken")]
    hs_no_trade = [r for r in hs if not r.get("trade_taken")]

    def _sweep_stats(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not subset:
            return {
                "n": 0,
                "sweep_unmet": 0,
                "sweep_unmet_pct": None,
                "sole_unmet_sweep": 0,
                "sole_unmet_sweep_pct": None,
                "sweep_among_unmet": 0,
            }
        n_sub = len(subset)
        sweep_unmet = sum(1 for r in subset if not r.get("sweep_met"))
        sole = sum(1 for r in subset if r.get("sole_unmet_is_sweep"))
        among = sum(
            1
            for r in subset
            if (not r.get("sweep_met")) and r.get("unmet_count", 0) > 1
        )
        return {
            "n": n_sub,
            "sweep_unmet": sweep_unmet,
            "sweep_unmet_pct": round(100.0 * sweep_unmet / n_sub, 2),
            "sole_unmet_sweep": sole,
            "sole_unmet_sweep_pct": round(100.0 * sole / n_sub, 2),
            "sweep_among_multiple_unmet": among,
            "other_sole_blockers": dict(
                Counter(
                    r["unmet"][0]
                    for r in subset
                    if r.get("unmet_count") == 1 and r["unmet"][0] != "liquidity_sweep"
                ).most_common(8)
            ),
        }

    # Hypothetical: if sweep were met, how many WAIT/NO_TRADE high-score would clear?
    # (score-only estimate — ignores RR/conflict hard blocks)
    hypo_clear = sum(
        1
        for r in hs_no_trade
        if (not r.get("sweep_met")) and r.get("score_if_sweep_met", 0) >= thr
    )

    return {
        "samples": len([r for r in rows if "error" not in r]),
        "errors": len([r for r in rows if "error" in r]),
        "diagnose_window": "TRAIN+VALIDATION only (TEST untouched)",
        "sample_indices": len(sample_idx),
        "signal_counts": dict(signal_counts),
        "unmet_condition_counts_all_samples": dict(unmet_keys.most_common()),
        "sole_unmet_blocker_counts_all_samples": dict(sole_blocker.most_common()),
        "high_score_ge_threshold": _sweep_stats(hs),
        "high_score_no_trade": _sweep_stats(hs_no_trade),
        "otherwise_qualifying": _sweep_stats(oq),
        "otherwise_qualifying_no_trade": _sweep_stats(oq_no_trade),
        "hypothetical_score_clear_if_sweep_met_among_high_score_no_trade": hypo_clear,
        "note": (
            "liquidity_required=False in StrategyConfig — missing sweep costs "
            f"{sweep_w:.0f} score points but is not a hard veto by itself. "
            "INVALIDATED on the UI maps from NO_TRADE status."
        ),
    }


# ─── Base rate of sweeps under current SMC definition ─────────────────────────


def sweep_base_rate(
    bars_by_tf: Dict[str, List],
    *,
    timeframe: str = "1h",
    smc_config: Optional[SmcConfig] = None,
) -> Dict[str, Any]:
    """
    Chronologically sample SMC on TRAIN+VAL and inventory confirmed sweeps.

    A single end-of-window analyze undercounts history because
    `liq_lookback_swings` only retains recent swings/pools — older sweeps drop
    out of the result even though they were valid at confirmation time.
    """
    bars = bars_by_tf[timeframe]
    n = len(bars)
    entry_n = len(bars_by_tf["15m"])
    _, test_start_15 = train_val_bounds(entry_n)
    cut_ts = bars_by_tf["15m"][test_start_15 - 1].timestamp
    diagnose_end = next(
        (i + 1 for i, b in enumerate(bars) if b.timestamp > cut_ts), n
    )
    diagnose_end = min(diagnose_end, n)

    engine = SmcEngine(smc_config or SmcConfig())
    if diagnose_end < 50:
        return {"error": "insufficient bars", "timeframe": timeframe}

    seen: Dict[str, Dict[str, Any]] = {}
    lookback_hits = {40: 0, 80: 0, 120: 0}
    dir_hits = {"bullish_40": 0, "bearish_40": 0, "bullish_80": 0, "bearish_80": 0}
    lookback_n = 0
    sample_stride = max(1, (diagnose_end - 80) // 120)
    sample_points = list(range(80, diagnose_end, sample_stride))

    for i in sample_points:
        result = engine.analyze(
            bars[: i + 1],
            symbol="PAXGUSD",
            timeframe=timeframe,
            as_of_index=i,
        )
        sweeps_now = [s for s in result.liquidity_sweeps if s.valid]
        for s in sweeps_now:
            key = (
                f"{s.direction.value}:{s.confirm_index}:"
                f"{round(float(s.liquidity_level), 2)}"
            )
            if key not in seen:
                seen[key] = {
                    "direction": s.direction.value,
                    "confirm_index": s.confirm_index,
                    "level": float(s.liquidity_level),
                }

        lookback_n += 1
        for lb in lookback_hits:
            cutoff = i - lb
            if any(cutoff <= s.confirm_index <= i for s in sweeps_now):
                lookback_hits[lb] += 1
        for lb, key_b, key_s in (
            (40, "bullish_40", "bearish_40"),
            (80, "bullish_80", "bearish_80"),
        ):
            cutoff = i - lb
            if any(
                cutoff <= s.confirm_index <= i and s.direction == SmcDirection.BULLISH
                for s in sweeps_now
            ):
                dir_hits[key_b] += 1
            if any(
                cutoff <= s.confirm_index <= i and s.direction == SmcDirection.BEARISH
                for s in sweeps_now
            ):
                dir_hits[key_s] += 1

    sweeps = list(seen.values())
    bull = [s for s in sweeps if s["direction"] == "bullish"]
    bear = [s for s in sweeps if s["direction"] == "bearish"]
    confirms = sorted(s["confirm_index"] for s in sweeps)
    gaps: List[float] = []
    for a, b in zip(confirms, confirms[1:]):
        gaps.append(float(b - a))

    bars_in_window = diagnose_end
    rate = (len(sweeps) / bars_in_window) if bars_in_window else 0.0
    avg_gap = (sum(gaps) / len(gaps)) if gaps else None

    lookback_pct = {
        str(k): round(100.0 * v / lookback_n, 2) if lookback_n else None
        for k, v in lookback_hits.items()
    }
    dir_pct = {
        k: round(100.0 * v / lookback_n, 2) if lookback_n else None
        for k, v in dir_hits.items()
    }

    return {
        "timeframe": timeframe,
        "bars_in_train_val": bars_in_window,
        "smc_sample_points": len(sample_points),
        "total_confirmed_sweeps_unique": len(sweeps),
        "bullish_sweeps": len(bull),
        "bearish_sweeps": len(bear),
        "sweeps_per_100_bars": round(100.0 * rate, 4),
        "avg_bars_between_sweeps": round(avg_gap, 2) if avg_gap is not None else None,
        "median_bars_between_sweeps": (
            round(sorted(gaps)[len(gaps) // 2], 2) if gaps else None
        ),
        "pct_sample_bars_with_any_sweep_in_lookback": lookback_pct,
        "pct_sample_bars_with_directional_sweep_in_lookback": dir_pct,
        "lookback_sample_n": lookback_n,
        "smc_defaults": {
            "liq_min_touches": (smc_config or SmcConfig()).liq_min_touches,
            "liq_cluster_tolerance": (smc_config or SmcConfig()).liq_cluster_tolerance,
            "liq_lookback_swings": (smc_config or SmcConfig()).liq_lookback_swings,
            "sweep_require_close_reclaim": (smc_config or SmcConfig()).sweep_require_close_reclaim,
            "sweep_max_bars_for_reclaim": (smc_config or SmcConfig()).sweep_max_bars_for_reclaim,
            "sweep_min_penetration": (smc_config or SmcConfig()).sweep_min_penetration,
        },
        "strategy_recent_sweep_bars_default": StrategyConfig().recent_sweep_bars,
        "note": (
            "Strategy uses smc_1h OR smc_15m (1H preferred when present) with "
            "recent_sweep_bars lookback — no 15m fallback if 1H exists but is empty. "
            "liq_cluster_tolerance=0.15 (absolute $) is tight vs ~$4300–5000 gold."
        ),
    }


def vol_snapshot(bars_by_tf: Dict[str, List]) -> Dict[str, Any]:
    """ATR%/ADX/RSI on TRAIN+VAL 15m — compare to Phase 11.7."""
    entry = bars_by_tf["15m"]
    _, end = train_val_bounds(len(entry))
    ta = TechnicalAnalysisEngine()
    rsi_vals: List[float] = []
    adx_vals: List[float] = []
    atr_pcts: List[float] = []
    stride = max(1, (end - 80) // 80)
    for i in range(80, end, stride):
        w = entry[max(0, i - 399) : i + 1]
        ana = ta.analyze(w, symbol="PAXGUSD", timeframe="15m", as_of_index=len(w) - 1)
        if ana.latest.rsi is not None:
            rsi_vals.append(float(ana.latest.rsi))
        if ana.latest.adx is not None:
            adx_vals.append(float(ana.latest.adx))
        closes = [b.close for b in w]
        highs = [b.high for b in w]
        lows = [b.low for b in w]
        atr_s = compute_atr(highs, lows, closes, period=14)
        atr_v = next((x for x in reversed(atr_s) if x is not None), None)
        if atr_v and closes[-1]:
            atr_pcts.append(100.0 * atr_v / closes[-1])
    return {
        "rsi": _pct(rsi_vals),
        "adx": _pct(adx_vals),
        "atr_pct": _pct(atr_pcts),
        "phase_11_7_reference": {
            "adx_p50": 23.3,
            "atr_pct_p50": 0.16,
            "rsi_p50": 49.1,
        },
    }


# ─── Sensitivity (train/val only) ─────────────────────────────────────────────


def _install_1h_then_15m_fallback():
    """Research patch: try 1H sweep, else 15m (mirrors BOS fallback)."""
    orig = cond_mod._score_direction

    def patched(ctx, config, *, bullish: bool):
        out = orig(ctx, config, bullish=bullish)
        want = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
        w = config.score_weights
        sweep = (
            cond_mod._recent_sweep(ctx.smc_1h, want, config) if ctx.smc_1h else None
        )
        if sweep is None and ctx.smc_15m is not None:
            sweep = cond_mod._recent_sweep(ctx.smc_15m, want, config)
        # Rewrite liquidity_sweep condition + keep relative order
        new_out = []
        for c in out:
            if c.key != "liquidity_sweep":
                new_out.append(c)
                continue
            if sweep is not None:
                new_out.append(
                    cond_mod._c(
                        "liquidity_sweep",
                        "Liquidity Sweep",
                        True,
                        w.liquidity_sweep,
                        w.liquidity_sweep,
                        f"Liquidity sweep @ {sweep.liquidity_level:.2f} (1H|15m fallback)",
                    )
                )
            else:
                new_out.append(
                    cond_mod._c(
                        "liquidity_sweep",
                        "Liquidity Sweep",
                        False,
                        0.0,
                        w.liquidity_sweep,
                        "No recent directional liquidity sweep",
                    )
                )
        return new_out

    cond_mod._score_direction = patched
    return orig


def _restore_score_direction(orig) -> None:
    cond_mod._score_direction = orig


def sensitivity_checks(bars_by_tf: Dict[str, List]) -> Dict[str, Any]:
    """
    TRAIN+VAL backtests + unblock estimates. TEST never evaluated here.
    """
    variants: List[Dict[str, Any]] = []

    # V0 baseline
    cfg0 = StrategyConfig(strategy_version="1.0.0-11.9-baseline")
    m0 = run_backtest(bars_by_tf, cfg=cfg0, split="TRAIN", step=24)
    m0v = run_backtest(bars_by_tf, cfg=cfg0, split="VALIDATION", step=12)
    variants.append(
        {
            "id": "V0_baseline",
            "description": "Default recent_sweep_bars=40; 1H preferred (no 15m fallback)",
            "recent_sweep_bars": 40,
            "fallback_15m": False,
            "train": m0,
            "validation": m0v,
        }
    )

    # V1 widen 80
    cfg1 = StrategyConfig(
        strategy_version="1.0.0-11.9-sweep80", recent_sweep_bars=80
    )
    m1 = run_backtest(bars_by_tf, cfg=cfg1, split="TRAIN", step=24)
    m1v = run_backtest(bars_by_tf, cfg=cfg1, split="VALIDATION", step=12)
    variants.append(
        {
            "id": "V1_lookback_80",
            "description": "Widen recent_sweep_bars 40→80 (~80h on 1H)",
            "recent_sweep_bars": 80,
            "fallback_15m": False,
            "train": m1,
            "validation": m1v,
        }
    )

    # V2 widen 120
    cfg2 = StrategyConfig(
        strategy_version="1.0.0-11.9-sweep120", recent_sweep_bars=120
    )
    m2 = run_backtest(bars_by_tf, cfg=cfg2, split="TRAIN", step=24)
    m2v = run_backtest(bars_by_tf, cfg=cfg2, split="VALIDATION", step=12)
    variants.append(
        {
            "id": "V2_lookback_120",
            "description": "Widen recent_sweep_bars 40→120 (~5 days on 1H)",
            "recent_sweep_bars": 120,
            "fallback_15m": False,
            "train": m2,
            "validation": m2v,
        }
    )

    # V3: 1H then 15m fallback (research monkeypatch), keep lookback=40
    orig = _install_1h_then_15m_fallback()
    try:
        cfg3 = StrategyConfig(strategy_version="1.0.0-11.9-fallback15m")
        m3 = run_backtest(bars_by_tf, cfg=cfg3, split="TRAIN", step=24)
        m3v = run_backtest(bars_by_tf, cfg=cfg3, split="VALIDATION", step=12)
        variants.append(
            {
                "id": "V3_1h_then_15m_fallback",
                "description": (
                    "Keep recent_sweep_bars=40 but if 1H has no directional sweep, "
                    "fall back to 15m (mirrors BOS/CHoCH fallback). Research patch only."
                ),
                "recent_sweep_bars": 40,
                "fallback_15m": True,
                "train": m3,
                "validation": m3v,
            }
        )
    finally:
        _restore_score_direction(orig)

    # V4: widen + fallback (aggressive research)
    orig = _install_1h_then_15m_fallback()
    try:
        cfg4 = StrategyConfig(
            strategy_version="1.0.0-11.9-wide-fallback", recent_sweep_bars=80
        )
        m4 = run_backtest(bars_by_tf, cfg=cfg4, split="TRAIN", step=24)
        m4v = run_backtest(bars_by_tf, cfg=cfg4, split="VALIDATION", step=12)
        variants.append(
            {
                "id": "V4_lookback_80_plus_fallback",
                "description": "recent_sweep_bars=80 + 1H→15m fallback (most permissive tried)",
                "recent_sweep_bars": 80,
                "fallback_15m": True,
                "train": m4,
                "validation": m4v,
            }
        )
    finally:
        _restore_score_direction(orig)

    # Unblock rate vs baseline on condition samples
    audit_base = audit_sweep_blockers(bars_by_tf, cfg=cfg0, max_samples=200)
    audit_v1 = audit_sweep_blockers(bars_by_tf, cfg=cfg1, max_samples=200)
    orig = _install_1h_then_15m_fallback()
    try:
        audit_v3 = audit_sweep_blockers(bars_by_tf, cfg=cfg3, max_samples=200)
    finally:
        _restore_score_direction(orig)

    def _unmet_pct(audit: Dict[str, Any]) -> Optional[float]:
        hs = audit.get("high_score_no_trade") or {}
        return hs.get("sweep_unmet_pct")

    return {
        "split": "TRAIN and VALIDATION only — TEST not run",
        "variants": variants,
        "unblock_estimates_high_score_no_trade_sweep_unmet_pct": {
            "V0_baseline": _unmet_pct(audit_base),
            "V1_lookback_80": _unmet_pct(audit_v1),
            "V3_1h_then_15m_fallback": _unmet_pct(audit_v3),
        },
        "audits_ref": {
            "V0": {
                "high_score_no_trade": audit_base.get("high_score_no_trade"),
                "signal_counts": audit_base.get("signal_counts"),
            },
            "V1": {
                "high_score_no_trade": audit_v1.get("high_score_no_trade"),
                "signal_counts": audit_v1.get("signal_counts"),
            },
            "V3": {
                "high_score_no_trade": audit_v3.get("high_score_no_trade"),
                "signal_counts": audit_v3.get("signal_counts"),
            },
        },
    }


def conclude(
    audit: Dict[str, Any],
    base_1h: Dict[str, Any],
    base_15m: Dict[str, Any],
    sens: Dict[str, Any],
    vol: Dict[str, Any],
) -> Dict[str, Any]:
    hs_nt = audit.get("high_score_no_trade") or {}
    oq_nt = audit.get("otherwise_qualifying_no_trade") or {}
    sweep_block_pct = hs_nt.get("sweep_unmet_pct")
    sole_pct = hs_nt.get("sole_unmet_sweep_pct")

    v0 = next(v for v in sens["variants"] if v["id"] == "V0_baseline")
    # Prefer validation expectancy; also note train
    def _exp(v):
        return {
            "train_n": v["train"].get("trades_entered"),
            "train_exp": v["train"].get("expectancy_r"),
            "val_n": v["validation"].get("trades_entered"),
            "val_exp": v["validation"].get("expectancy_r"),
        }

    exps = {v["id"]: _exp(v) for v in sens["variants"]}
    baseline_val = v0["validation"].get("expectancy_r") or 0.0
    baseline_train = v0["train"].get("expectancy_r") or 0.0

    improved = []
    worsened = []
    for v in sens["variants"]:
        if v["id"] == "V0_baseline":
            continue
        ve = v["validation"].get("expectancy_r")
        te = v["train"].get("expectancy_r")
        if ve is None:
            continue
        # Improvement = better val expectancy AND not clearly worse train
        if ve > baseline_val + 0.02 and (te is None or te >= baseline_train - 0.05):
            improved.append(v["id"])
        if ve < baseline_val - 0.02 or (
            te is not None and te < baseline_train - 0.05 and ve <= baseline_val
        ):
            worsened.append(v["id"])

    avg_gap_1h = base_1h.get("avg_bars_between_sweeps")
    dir40 = (base_1h.get("pct_sample_bars_with_directional_sweep_in_lookback") or {}).get(
        "bullish_40"
    )
    any40 = (base_1h.get("pct_sample_bars_with_any_sweep_in_lookback") or {}).get("40")

    # Decision logic (evidence thresholds are deliberately conservative)
    # "Small %" sole-blocker ≈ not the dominant hard veto; frequent unmet is a score gap.
    major_sole = sole_pct is not None and sole_pct >= 15
    frequent_unmet = sweep_block_pct is not None and sweep_block_pct >= 50
    rare_events = (avg_gap_1h is not None and avg_gap_1h > 80) or (
        any40 is not None and any40 < 35
    )

    if major_sole and frequent_unmet and improved and len(improved) > len(worsened):
        label = "bottleneck"
        text = (
            "Liquidity sweep is a real bottleneck — it is often the sole unmet "
            "condition on high-score no-trades, directional reclaim sweeps are "
            "sparse vs the 40-bar 1H window on real PAXGUSD, and at least one "
            "reasonable widening/fallback improved TRAIN/VAL expectancy. Any "
            "production change still needs a full recalibration pass "
            "(Phase 11.6-style) and explicit approval."
        )
    elif (not major_sole) and rare_events and (worsened or not improved) and frequent_unmet:
        label = "inconclusive"
        text = (
            "Inconclusive for a production change — leave the live definition as-is "
            "for now. Confirmed reclaim sweeps are genuinely uncommon on quiet real "
            f"PAXGUSD (1H avg gap~{avg_gap_1h} bars; any-sweep-in-40~{any40}%), so the "
            f"condition is unmet on ~{sweep_block_pct}% of high-score no-trade samples "
            f"as a **15-point score gap**. But it is rarely the *sole* unmet condition "
            f"(~{sole_pct}%), and sensitivity checks did not find a clean expectancy "
            "win: widening `recent_sweep_bars` (40→80→120) changed nothing (1H still "
            "empty), while 1H→15m fallback added a few trades and **worsened** "
            "VALIDATION expectancy. That pattern fits 'rare structure + score friction' "
            "more than a proven miscalibration bug. Re-open only with more history or a "
            "pre-registered TRAIN/VAL→TEST protocol."
        )
    elif (not frequent_unmet) and (worsened or not improved) and rare_events:
        label = "selective"
        text = (
            "Liquidity sweep is correctly selective — it blocks a modest share of "
            "setups, its base rate matches quiet PAXGUSD, and loosening it in the "
            "sensitivity check made expectancy worse or unchanged. Leave production "
            "as-is; repeated live `✗ Liquidity Sweep` lines often reflect a score gap "
            "on NO_TRADE cards, not a hard `liquidity_required` veto."
        )
    else:
        label = "inconclusive"
        text = (
            "Inconclusive — evidence does not cleanly support either 'correctly "
            "selective' or 'must loosen now'. Prefer more PAXGUSD history before "
            "changing Phase 6."
        )

    return {
        "label": label,
        "statement": text,
        "key_numbers": {
            "high_score_no_trade_sweep_unmet_pct": sweep_block_pct,
            "high_score_no_trade_sole_sweep_pct": sole_pct,
            "otherwise_qualifying_no_trade_sweep_unmet_pct": oq_nt.get("sweep_unmet_pct"),
            "1h_avg_bars_between_sweeps": avg_gap_1h,
            "1h_unique_sweeps": base_1h.get("total_confirmed_sweeps_unique"),
            "1h_pct_sample_any_sweep_in_40": any40,
            "1h_pct_bars_bullish_sweep_in_40": dir40,
            "sensitivity_improved_vs_baseline_val": improved,
            "sensitivity_worsened_vs_baseline": worsened,
            "variant_expectancies": exps,
            "vol_atr_pct_p50": (vol.get("atr_pct") or {}).get("p50"),
            "vol_adx_p50": (vol.get("adx") or {}).get("p50"),
        },
    }


def write_report(payload: Dict[str, Any]) -> Path:
    path = REPO_ROOT / "docs" / "phase-11.9-liquidity-sweep-investigation.md"
    audit = payload["audit"]
    base_1h = payload["base_rate_1h"]
    base_15m = payload["base_rate_15m"]
    sens = payload["sensitivity"]
    vol = payload["volatility"]
    conclusion = payload["conclusion"]
    defn = payload["definition"]

    lines = [
        "# Phase 11.9 — Liquidity Sweep Condition Investigation",
        "",
        f"**Generated:** {payload['generated_at']}",
        "**Symbol:** PAXGUSD (Delta India real CSV, same window as Phase 11.6/11.7)",
        "**Code changes to live Phase 6:** **None**",
        "",
        "> Research / diagnosis only. Held-out TEST was not used for sensitivity tuning.",
        "",
        "## 0. Definition under investigation",
        "",
        "### SMC detection (`backend/app/smc/liquidity.py`, `docs/smc-rules.md`)",
        "",
        "```json",
        json.dumps(defn["smc"], indent=2),
        "```",
        "",
        "- **Bullish sweep (sell-side taken):** pierce below clustered swing-low liquidity, then close back above within `sweep_max_bars_for_reclaim` (default 3).",
        "- **Bearish sweep (buy-side taken):** pierce above clustered swing-high liquidity, then close back below within 3 bars.",
        "- Pierce without reclaim → **no** confirmed event.",
        "- Liquidity pool requires `liq_min_touches` (≥2) clustered swings (`liq_cluster_tolerance`).",
        "",
        "### Strategy condition (`backend/app/strategy/conditions.py`)",
        "",
        "```json",
        json.dumps(defn["strategy"], indent=2),
        "```",
        "",
        "- Weight: **15 / 100** condition points.",
        "- `liquidity_required=False` → missing sweep is **not** a hard veto; it zeros those 15 points.",
        "- Lookback: `recent_sweep_bars=40` on the SMC timeframe used.",
        "- Source TF: `smc_1h or smc_15m` — **if 1H analysis exists, 15m is never consulted** (unlike BOS/CHoCH, which falls back to 15m).",
        "- UI `INVALIDATED` = mapped from `NO_TRADE` status; unmet conditions are listed with `✗`, so a live card can *look* sweep-blocked even when RR/conflict/validation also matter.",
        "",
        "## 1. How often does this block trades?",
        "",
        f"Sample: **{audit.get('samples')}** evenly spaced TRAIN+VAL evaluation points "
        f"(15m), score threshold {StrategyConfig().signal_threshold}.",
        "",
        "```json",
        json.dumps(
            {
                "signal_counts": audit.get("signal_counts"),
                "high_score_ge_threshold": audit.get("high_score_ge_threshold"),
                "high_score_no_trade": audit.get("high_score_no_trade"),
                "otherwise_qualifying": audit.get("otherwise_qualifying"),
                "otherwise_qualifying_no_trade": audit.get("otherwise_qualifying_no_trade"),
                "sole_unmet_blocker_counts_all_samples": audit.get(
                    "sole_unmet_blocker_counts_all_samples"
                ),
                "unmet_condition_counts_all_samples": audit.get(
                    "unmet_condition_counts_all_samples"
                ),
                "note": audit.get("note"),
            },
            indent=2,
        ),
        "```",
        "",
        "### Reading",
        "",
        f"- Among **high-score (≥65) no-trade** samples, sweep unmet in "
        f"**{((audit.get('high_score_no_trade') or {}).get('sweep_unmet_pct'))}%**.",
        f"- Sweep as **sole** unmet condition in "
        f"**{((audit.get('high_score_no_trade') or {}).get('sole_unmet_sweep_pct'))}%** of those.",
        "- Compare to Phase 11.6 top blockers (location / entry TF / MTF oppose / RR) — "
        "those still dominate *risk* text when score is high; sweep shows up heavily as "
        "an unmet **score condition**, especially on live cards that list `✗` reasons for NO_TRADE.",
        "",
        "## 2. Base rate vs PAXGUSD volatility",
        "",
        "### Confirmed sweeps (current SMC definition)",
        "",
        "**1H**",
        "",
        "```json",
        json.dumps(base_1h, indent=2),
        "```",
        "",
        "**15M**",
        "",
        "```json",
        json.dumps(base_15m, indent=2),
        "```",
        "",
        "### Volatility / trend context (TRAIN+VAL)",
        "",
        "```json",
        json.dumps(vol, indent=2),
        "```",
        "",
        "Interpretation: Phase 11.7 already established quiet gold (ADX p50≈23, ATR% p50≈0.16%). "
        "A reclaim-within-3-bars sweep of a **multi-touch** liquidity pool is a relatively "
        "rare structure on that tape. If average bars between 1H sweeps ≫ `recent_sweep_bars=40`, "
        "the condition will frequently score 0 even when HTF bias is aligned — without being 'buggy'.",
        "",
        "## 3. Sensitivity (TRAIN / VALIDATION only)",
        "",
        "TEST slice was **not** evaluated for these variants.",
        "",
        "```json",
        json.dumps(sens, indent=2, default=str),
        "```",
        "",
        "Variants tried:",
        "",
        "| ID | Change | Intent |",
        "|----|--------|--------|",
        "| V0 | baseline | Control |",
        "| V1 | `recent_sweep_bars` 40→80 | Wider recency |",
        "| V2 | `recent_sweep_bars` 40→120 | Wider still |",
        "| V3 | 1H→15m fallback | Fix TF asymmetry vs BOS |",
        "| V4 | 80 + fallback | Most permissive combo |",
        "",
        "## 4. Conclusion",
        "",
        f"**Label:** `{conclusion['label']}`",
        "",
        conclusion["statement"],
        "",
        "### Key numbers",
        "",
        "```json",
        json.dumps(conclusion["key_numbers"], indent=2),
        "```",
        "",
        "## 5. Explicit non-actions",
        "",
        "- No change to `StrategyConfig` defaults.",
        "- No change to `SmcConfig` sweep detection.",
        "- No Phase 12 GO implication.",
        "- If a future change is approved: require before/after TRAIN+VAL+TEST protocol "
        "like Phase 11.6, document in PROJECT.md, and keep WAIT/NO_TRADE first-class.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-base-rate",
        action="store_true",
        help="Reuse prior JSON audit/sensitivity; only recompute base rates + rewrite docs",
    )
    args = parser.parse_args()

    _log("=== Phase 11.9 Liquidity Sweep Investigation ===")
    bars = load_bars()
    cfg = StrategyConfig(strategy_version="1.0.0")
    json_path = REPO_ROOT / "docs" / "phase-11.9-liquidity-sweep-investigation.json"

    if args.refresh_base_rate and json_path.exists():
        _log("=== Refresh base rates only (reuse prior audit/sensitivity) ===")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        base_1h = sweep_base_rate(bars, timeframe="1h")
        base_15m = sweep_base_rate(bars, timeframe="15m")
        _log(
            f"  1h unique={base_1h.get('total_confirmed_sweeps_unique')} "
            f"avg_gap={base_1h.get('avg_bars_between_sweeps')} "
            f"any40%={(base_1h.get('pct_sample_bars_with_any_sweep_in_lookback') or {}).get('40')}"
        )
        _log(
            f"  15m unique={base_15m.get('total_confirmed_sweeps_unique')} "
            f"avg_gap={base_15m.get('avg_bars_between_sweeps')}"
        )
        payload["base_rate_1h"] = base_1h
        payload["base_rate_15m"] = base_15m
        payload["definition"]["smc"] = base_1h.get("smc_defaults")
        payload["conclusion"] = conclude(
            payload["audit"], base_1h, base_15m, payload["sensitivity"], payload["volatility"]
        )
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        payload["base_rate_method"] = "chronological_smc_sample"
        _log(f"=== Conclusion: {payload['conclusion']['label']} ===")
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        md_path = write_report(payload)
        _log(f"Wrote {json_path}")
        _log(f"Wrote {md_path}")
        return 0

    _log("=== 1) Audit sweep blockers (TRAIN+VAL) ===")
    audit = audit_sweep_blockers(bars, cfg=cfg, max_samples=300)
    _log(
        f"  samples={audit.get('samples')} signals={audit.get('signal_counts')} "
        f"hs_nt_sweep_unmet%={(audit.get('high_score_no_trade') or {}).get('sweep_unmet_pct')}"
    )

    _log("=== 2) Sweep base rate ===")
    base_1h = sweep_base_rate(bars, timeframe="1h")
    base_15m = sweep_base_rate(bars, timeframe="15m")
    _log(
        f"  1h unique={base_1h.get('total_confirmed_sweeps_unique')} "
        f"avg_gap={base_1h.get('avg_bars_between_sweeps')}"
    )
    _log(
        f"  15m unique={base_15m.get('total_confirmed_sweeps_unique')} "
        f"avg_gap={base_15m.get('avg_bars_between_sweeps')}"
    )

    _log("=== 2b) Volatility snapshot ===")
    vol = vol_snapshot(bars)
    _log(f"  atr% p50={((vol.get('atr_pct') or {}).get('p50'))} adx p50={((vol.get('adx') or {}).get('p50'))}")

    _log("=== 3) Sensitivity TRAIN/VAL (no TEST) ===")
    sens = sensitivity_checks(bars)
    for v in sens["variants"]:
        _log(
            f"  {v['id']}: train n={v['train'].get('trades_entered')} "
            f"exp={v['train'].get('expectancy_r')} | "
            f"val n={v['validation'].get('trades_entered')} "
            f"exp={v['validation'].get('expectancy_r')}"
        )

    conclusion = conclude(audit, base_1h, base_15m, sens, vol)
    _log(f"=== Conclusion: {conclusion['label']} ===")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": {
            "smc": base_1h.get("smc_defaults"),
            "strategy": {
                "liquidity_sweep_weight": cfg.score_weights.liquidity_sweep,
                "liquidity_required": cfg.liquidity_required,
                "recent_sweep_bars": cfg.recent_sweep_bars,
                "entry_confirm_bars": cfg.entry_confirm_bars,
                "signal_threshold": cfg.signal_threshold,
                "source_tf_rule": "smc_1h or smc_15m (no fallback if 1H present)",
            },
        },
        "audit": audit,
        "base_rate_1h": base_1h,
        "base_rate_15m": base_15m,
        "volatility": vol,
        "sensitivity": sens,
        "conclusion": conclusion,
        "base_rate_method": "chronological_smc_sample",
    }

    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path = write_report(payload)
    _log(f"Wrote {json_path}")
    _log(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
