#!/usr/bin/env python3
"""
Phase 11.6 — expand Delta history, diagnose, optionally recalibrate, re-backtest.

Hard rules:
  - No look-ahead / no test-slice threshold tuning
  - WAIT/NO_TRADE remain valid
  - Report honest go/no-go
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
from app.core.config import get_settings  # noqa: E402
from app.market.deps import get_memory_repository, get_provider, reset_market_singletons  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES, Timeframe  # noqa: E402
from app.market.service import MarketDataService  # noqa: E402
from app.market.validator import OHLCVValidator  # noqa: E402
from app.mtf.sync import candle_close_time  # noqa: E402
from app.strategy.config import StrategyConfig  # noqa: E402
from app.strategy.engine import StrategyEngine  # noqa: E402
from app.strategy.schemas import SignalDirection  # noqa: E402
from app.ta.engine import TechnicalAnalysisEngine  # noqa: E402
from app.ta.indicators import atr as compute_atr  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


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


async def expand_backfill(*, force: bool = False) -> Dict[str, Any]:
    """Pull maximum available Delta history for PAXGUSD."""
    out_dir = REPO_ROOT / "data" / "historical"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Reuse existing max-window CSVs unless force=True
    if not force:
        existing = {}
        ok = True
        for tf in Timeframe:
            path = out_dir / f"PAXGUSD_{tf.value}.csv"
            if not path.exists():
                ok = False
                break
            # crude line count
            n = sum(1 for _ in path.open(encoding="utf-8")) - 1
            existing[tf.value] = {"bars": n, "csv": path.name, "reused": True}
        if ok and existing.get("15m", {}).get("bars", 0) >= 10_000:
            _log("  reusing existing max-window CSVs (skip live backfill)")
            return existing

    reset_market_singletons()
    get_settings.cache_clear()
    service = MarketDataService(
        provider=get_provider(),
        repository=get_memory_repository(),
        validator=OHLCVValidator(),
    )
    end = datetime.now(timezone.utc)
    # Product history observed from ~2026-02-19; request generously
    start = end - timedelta(days=400)
    info: Dict[str, Any] = {}
    for tf in Timeframe:
        bars, _ = await service.ingest_historical(
            "PAXGUSD", tf, start, end, persist=True
        )
        path = out_dir / f"PAXGUSD_{tf.value}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "source",
                ],
            )
            w.writeheader()
            for b in bars:
                w.writerow(
                    {
                        "timestamp": b.timestamp.isoformat(),
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "volume": b.volume,
                        "source": b.source,
                    }
                )
        info[tf.value] = {
            "bars": len(bars),
            "first": bars[0].timestamp.isoformat() if bars else None,
            "last": bars[-1].timestamp.isoformat() if bars else None,
            "csv": path.name,
        }
        _log(f"  backfill {tf.value}: n={len(bars)} -> {path.name}")
    return info


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


def run_backtest(
    bars_by_tf: Dict[str, List],
    *,
    cfg: Optional[StrategyConfig] = None,
    split: str = "ALL",
    step: int = 4,
    warmup: int = 80,
    max_context_bars: int = 400,
) -> Dict[str, Any]:
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
        strategy_version=(cfg.strategy_version if cfg else "1.0.0"),
        signal_mode="RULE_ONLY",
        step=step,
    )
    engine = BacktestEngine(
        bcfg, strategy_config=cfg or StrategyConfig(strategy_version="1.0.0")
    )
    result = engine.run(bars_by_tf, split_segment=split)
    return _metrics(result)


def diagnose_scores(
    bars_by_tf: Dict[str, List],
    *,
    cfg: StrategyConfig,
    max_samples: int = 200,
) -> Dict[str, Any]:
    """Sample strategy scores / indicator ranges on TRAIN+VAL only (no TEST peek)."""
    entry = bars_by_tf["15m"]
    n = len(entry)
    eval_start, eval_end, _ = chronological_eval_bounds(n, segment="TRAIN")
    # Include validation for diagnosis distributions (still before TEST)
    _, test_start, _ = chronological_eval_bounds(n, segment="TEST")
    diagnose_end = test_start  # exclusive — never look at TEST

    strategy = StrategyEngine(config=cfg)
    ta_engine = TechnicalAnalysisEngine()

    scores: List[int] = []
    dirs: Counter = Counter()
    near_miss = 0  # wait band 50-64
    rsi_vals: List[float] = []
    adx_vals: List[float] = []
    atr_pcts: List[float] = []
    reasons_block: Counter = Counter()

    # Evenly sample indices in [warmup, diagnose_end)
    start_i = max(80, eval_start)
    usable = list(range(start_i, diagnose_end))
    if not usable:
        return {"error": "no train/val bars after warmup"}
    stride = max(1, len(usable) // max_samples)
    sample_idx = usable[::stride][:max_samples]

    for i in sample_idx:
        bar = entry[i]
        as_of = candle_close_time(bar, "15m")
        windowed = {
            tf: [b for b in bars if b.timestamp <= bar.timestamp][-400:]
            for tf, bars in bars_by_tf.items()
        }
        try:
            result = strategy.analyze(
                windowed, symbol="PAXGUSD", as_of=as_of, timeframes=list(ANALYSIS_TIMEFRAMES)
            )
        except Exception as exc:  # noqa: BLE001
            reasons_block[f"exception:{type(exc).__name__}"] += 1
            continue

        scores.append(int(result.score))
        dirs[result.signal.value] += 1
        if cfg.wait_threshold <= result.score < cfg.signal_threshold:
            near_miss += 1
        if result.signal == SignalDirection.NO_TRADE and result.score >= cfg.signal_threshold:
            for r in (result.risks or result.reasons or [])[:2]:
                reasons_block[str(r)[:80]] += 1

        # Indicator snapshot on 15m
        w15 = windowed.get("15m") or []
        if len(w15) >= 50:
            ta = ta_engine.analyze(
                w15, symbol="PAXGUSD", timeframe="15m", as_of_index=len(w15) - 1
            )
            if ta.latest.rsi is not None:
                rsi_vals.append(float(ta.latest.rsi))
            if ta.latest.adx is not None:
                adx_vals.append(float(ta.latest.adx))
            closes = [b.close for b in w15]
            highs = [b.high for b in w15]
            lows = [b.low for b in w15]
            atr_s = compute_atr(highs, lows, closes, period=14)
            atr_v = next((x for x in reversed(atr_s) if x is not None), None)
            if atr_v and closes[-1]:
                atr_pcts.append(100.0 * atr_v / closes[-1])

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

    score_hist = Counter()
    for sc in scores:
        if sc >= 80:
            score_hist["80+"] += 1
        elif sc >= 65:
            score_hist["65-79"] += 1
        elif sc >= 50:
            score_hist["50-64"] += 1
        else:
            score_hist["<50"] += 1

    return {
        "samples": len(scores),
        "diagnose_window": "TRAIN+VALIDATION only (TEST untouched)",
        "direction_counts": dict(dirs),
        "score_bands": dict(score_hist),
        "score_distribution": _pct([float(s) for s in scores]),
        "near_miss_wait_band_count": near_miss,
        "near_miss_rate": round(near_miss / max(len(scores), 1), 4),
        "blocked_high_score_reasons": dict(reasons_block.most_common(8)),
        "rsi_distribution": _pct(rsi_vals),
        "adx_distribution": _pct(adx_vals),
        "atr_pct_distribution": _pct(atr_pcts),
        "synthetic_reference_notes": {
            "mock_base_price_era": "~2300 then ~4340",
            "mtf_rsi_bull_bear": ">=55 / <=45",
            "mtf_adx_filter": ">=20",
            "strategy_signal_threshold": cfg.signal_threshold,
            "strategy_wait_threshold": cfg.wait_threshold,
            "atr_pct_on_real_gold_~4340": "typically ~0.1% per 1h ATR vs larger relative moves on synthetic",
        },
        "phase10_zero_trade_hypothesis": {
            "measurement_bug": (
                "Prior engine sliced TEST first then applied warmup_bars on the short "
                "slice — if TEST length < warmup, zero evaluations. Fixed in Phase 11.6 "
                "to keep full-series context and evaluate only inside segment bounds."
            ),
            "strategy_conservatism": (
                "Score>=65 requires multi-condition SMC confluence; WAIT/NO_TRADE "
                "dominance may be correct on ranging real gold."
            ),
        },
    }


def propose_recalibration(diagnosis: Dict[str, Any]) -> tuple[StrategyConfig, List[Dict[str, Any]]]:
    """
    Propose threshold changes from TRAIN/VAL distributions only.

    Rule: never lower thresholds just to force trades. Only adjust when evidence
    shows synthetic-era gates are misaligned with real distributions.
    """
    changes: List[Dict[str, Any]] = []
    cfg = StrategyConfig(strategy_version="1.0.1-real-recal")

    bands = diagnosis.get("score_bands") or {}
    score_dist = diagnosis.get("score_distribution") or {}
    near_miss_rate = float(diagnosis.get("near_miss_rate") or 0)
    dirs = diagnosis.get("direction_counts") or {}
    buy_sell = int(dirs.get("BUY", 0)) + int(dirs.get("SELL", 0))
    samples = int(diagnosis.get("samples") or 0)

    # Default: keep 65/50 unless distributions show mass piled in 50-64 with
    # structural confluence already partial (near-miss) AND almost no BUY/SELL.
    # Even then, only modest move of signal_threshold toward p90 of scores if
    # p90 is below 65 — i.e. thresholds above real attainable scores.
    p90 = score_dist.get("p90")
    p50 = score_dist.get("p50")

    if (
        samples >= 50
        and buy_sell == 0
        and p90 is not None
        and p90 < cfg.signal_threshold
        and near_miss_rate >= 0.15
    ):
        # Real attainable scores rarely reach 65; move gate to ceil(p90) but
        # never below wait_threshold+5, and never below 55 (anti force-trades).
        new_signal = max(55.0, min(cfg.signal_threshold, float(p90)))
        # If p90 is e.g. 58, set signal to 58 — still requires top-decile setups
        if new_signal < cfg.signal_threshold:
            changes.append(
                {
                    "field": "signal_threshold",
                    "before": cfg.signal_threshold,
                    "after": new_signal,
                    "rationale": (
                        f"On TRAIN+VAL, score p90={p90} < old gate 65 with "
                        f"near_miss_rate={near_miss_rate:.2%} and 0 BUY/SELL samples. "
                        "Gate moved to real top-decile, not below 55."
                    ),
                }
            )
            cfg.signal_threshold = new_signal

    # Soften HTF hard alignment only if many high scores are blocked by it
    blocked = diagnosis.get("blocked_high_score_reasons") or {}
    htf_blocks = sum(v for k, v in blocked.items() if "HTF" in k or "alignment" in k.lower())
    if htf_blocks >= max(3, samples // 20) and buy_sell <= samples * 0.02:
        changes.append(
            {
                "field": "minimum_htf_alignment",
                "before": True,
                "after": False,
                "rationale": (
                    f"{htf_blocks} high-score samples blocked by HTF/4H alignment on "
                    "TRAIN+VAL while BUY/SELL almost never clears. Alignment remains "
                    "in the score via higher_tf_bias/structure_4h weights; hard veto removed."
                ),
            }
        )
        cfg.minimum_htf_alignment = False

    # Slightly reduce high-vol penalty if ATR% on real is structurally lower and
    # HIGH band still fires often — only if we see vol-related blocks.
    vol_blocks = sum(
        v for k, v in blocked.items() if "volatil" in k.lower() or "ATR" in k
    )
    atr_p50 = (diagnosis.get("atr_pct_distribution") or {}).get("p50")
    if vol_blocks >= 3 and atr_p50 is not None and atr_p50 < 0.25:
        changes.append(
            {
                "field": "high_volatility_penalty",
                "before": cfg.high_volatility_penalty,
                "after": 5.0,
                "rationale": (
                    f"Real 15m ATR% p50={atr_p50} is small in absolute gold terms; "
                    f"{vol_blocks} vol-related blocks observed. Penalty 8→5 (still active)."
                ),
            }
        )
        cfg.high_volatility_penalty = 5.0

    if not changes:
        changes.append(
            {
                "field": "(none)",
                "before": None,
                "after": None,
                "rationale": (
                    "TRAIN+VAL distributions do not justify lowering entry gates. "
                    "Keeping signal_threshold=65 / wait_threshold=50. "
                    "Measurement fix (full-series warmup) is the primary change."
                ),
            }
        )
        cfg = StrategyConfig(strategy_version="1.0.0")  # unchanged thresholds

    return cfg, changes


def write_diagnosis(payload: Dict[str, Any]) -> Path:
    path = REPO_ROOT / "docs" / "phase-11.6-diagnosis.md"
    lines = [
        "# Phase 11.6 — Strategy Diagnosis (Real PAXGUSD / Delta India)",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        "",
        "> Diagnosis written **before** threshold changes. No test-slice peeking.",
        "",
        "## 1. Expanded historical window",
        "",
        "```json",
        json.dumps(payload.get("backfill"), indent=2, default=str),
        "```",
        "",
        "## 2. Baseline backtests (pre-recalibration)",
        "",
        "### Original Phase 11.5 reference (small window / prior run)",
        "",
        "```json",
        json.dumps(payload.get("baseline_original_ref"), indent=2),
        "```",
        "",
        "### Expanded window — ALL (pre-recal, default thresholds)",
        "",
        "```json",
        json.dumps(payload.get("baseline_expanded_all"), indent=2),
        "```",
        "",
        "### Expanded window — TEST (pre-recal, after measurement fix)",
        "",
        "```json",
        json.dumps(payload.get("baseline_expanded_test"), indent=2),
        "```",
        "",
        "## 3. Root cause — Phase 10 zero trades",
        "",
        "```json",
        json.dumps(payload.get("diagnosis"), indent=2, default=str),
        "```",
        "",
        "## 4. Proposed recalibration (TRAIN/VAL evidence only)",
        "",
        "```json",
        json.dumps(payload.get("proposed_changes"), indent=2, default=str),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_results(payload: Dict[str, Any]) -> Path:
    path = REPO_ROOT / "docs" / "phase-11.6-recalibration-results.md"
    lines = [
        "# Phase 11.6 — Recalibration Results & Go/No-Go",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        "",
        "## Comparison table",
        "",
        "```json",
        json.dumps(payload.get("comparison"), indent=2, default=str),
        "```",
        "",
        "## Applied threshold changes",
        "",
        "```json",
        json.dumps(payload.get("applied_changes"), indent=2, default=str),
        "```",
        "",
        "## Phase 10 held-out TEST (post-recal)",
        "",
        "```json",
        json.dumps(payload.get("phase10_test"), indent=2, default=str),
        "```",
        "",
        "## Go / No-Go decision",
        "",
        payload.get("decision_text", ""),
        "",
        f"**Decision:** `{payload.get('decision')}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main_async() -> int:
    settings = get_settings()
    if settings.market_data_provider.lower().strip() in ("mock",):
        _log("ERROR: use MARKET_DATA_PROVIDER=delta_india")
        return 2

    _log("=== Step 1: Expand Delta historical backfill ===")
    backfill = await expand_backfill()

    _log("=== Load bars ===")
    bars = load_bars()
    default_cfg = StrategyConfig(strategy_version="1.0.0")

    _log("=== Step 1b: Expanded baseline backtest (pre-recal) ===")
    # step=24 on ~16k bars ≈ 680 strategy evals (honest expanded sample, tractable CPU)
    baseline_all = run_backtest(bars, cfg=default_cfg, split="ALL", step=24)
    _log(f"  ALL: {baseline_all}")
    baseline_test = run_backtest(bars, cfg=default_cfg, split="TEST", step=12)
    _log(f"  TEST: {baseline_test}")

    original_ref = {
        "source": "Phase 11.5 validate_phase_11_5 Delta run (conversation)",
        "trades_entered": 12,
        "win_rate": 0.333333,
        "expectancy_r": -0.193054,
        "max_drawdown_pct": 5.7784,
        "phase10_test_trades": 0,
        "note": "Smaller capped window + TEST warmup-after-slice measurement artifact",
    }

    _log("=== Step 2: Diagnose on TRAIN+VAL only ===")
    diagnosis = diagnose_scores(bars, cfg=default_cfg, max_samples=80)
    _log(f"  directions={diagnosis.get('direction_counts')} bands={diagnosis.get('score_bands')}")

    proposed_cfg, proposed_changes = propose_recalibration(diagnosis)
    diag_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backfill": backfill,
        "baseline_original_ref": original_ref,
        "baseline_expanded_all": baseline_all,
        "baseline_expanded_test": baseline_test,
        "diagnosis": diagnosis,
        "proposed_changes": proposed_changes,
    }
    dpath = write_diagnosis(diag_payload)
    _log(f"Wrote {dpath}")

    _log("=== Step 3–4: Apply recalibration (if any) and re-backtest ===")
    post_all = run_backtest(bars, cfg=proposed_cfg, split="ALL", step=24)
    post_test = run_backtest(bars, cfg=proposed_cfg, split="TEST", step=12)
    post_val = run_backtest(bars, cfg=proposed_cfg, split="VALIDATION", step=12)
    _log(f"  post ALL: {post_all}")
    _log(f"  post VAL: {post_val}")
    _log(f"  post TEST: {post_test}")

    # Honest gate — prefer held-out TEST over in-sample ALL; do not GO on
    # barely-positive ALL when TEST is clearly negative or n is tiny.
    trades = int(post_all.get("trades_entered") or 0)
    exp = float(post_all.get("expectancy_r") or 0.0)
    pre_exp = float(baseline_all.get("expectancy_r") or 0.0)
    test_trades = int(post_test.get("trades_entered") or 0)
    test_exp = float(post_test.get("expectancy_r") or 0.0)
    val_exp = float(post_val.get("expectancy_r") or 0.0)

    if trades < 30:
        decision = "NO_GO"
        decision_text = (
            f"NO-GO for Phase 12. Expanded real-data ALL backtest has only n={trades} "
            f"trades (expectancy_r={exp:.4f}). Sample is too small to trust — a handful "
            "of outcomes can dominate. Do not paper-trade yet. Next steps: revisit Phase 6 "
            "confluence structure (not only thresholds), or accumulate more live history "
            "as Delta PAXGUSD listing ages past the ~Feb 2026 start."
        )
    elif exp <= 0:
        decision = "NO_GO"
        decision_text = (
            f"NO-GO for Phase 12. After expanded backfill and recalibration attempt, "
            f"ALL-window expectancy remains {exp:.4f}R on n={trades} trades. "
            "Paper trading would only confirm a losing rule set. Next steps: structural "
            "review of Phase 6 conditions (SMC confluence / HTF gates), not further "
            "threshold grinding on this sample."
        )
    elif test_trades == 0:
        decision = "NO_GO"
        decision_text = (
            f"NO-GO for Phase 12 despite ALL expectancy {exp:.4f}R (n={trades}). "
            "Held-out TEST produced 0 trades — cannot claim out-of-sample viability. "
            "WAIT dominance on TEST may be honest market behavior; still not enough "
            "evidence to start paper trading."
        )
    elif test_trades < 15 or test_exp < 0:
        decision = "NO_GO"
        decision_text = (
            f"NO-GO for Phase 12. Held-out TEST expectancy={test_exp:.4f}R on "
            f"n={test_trades} trades (ALL={exp:.4f}R n={trades}; VAL={val_exp:.4f}R; "
            f"pre-recal ALL={pre_exp:.4f}R). Out-of-sample edge is unproven or negative; "
            "sample still too thin for a confident gate. Do not start paper trading. "
            "Next steps: (1) revisit Phase 6 confluence structure beyond threshold tweaks, "
            "(2) wait for longer Delta PAXGUSD history, (3) keep measurement fix "
            "(full-series warmup) but retain default thresholds unless VAL+TEST both improve."
        )
    elif exp < pre_exp and test_exp <= float(baseline_test.get("expectancy_r") or 0.0):
        decision = "NO_GO"
        decision_text = (
            f"NO-GO for Phase 12. Recalibration worsened or failed to improve results "
            f"(post ALL={exp:.4f}R vs pre ALL={pre_exp:.4f}R; TEST={test_exp:.4f}R). "
            "Do not adopt threshold changes that do not help held-out performance."
        )
    else:
        decision = "GO"
        decision_text = (
            f"GO for Phase 12 paper trading (research only). ALL expectancy {exp:.4f}R "
            f"on n={trades} trades; TEST expectancy {test_exp:.4f}R on n={test_trades}. "
            "Treat paper results as provisional and keep WAIT/NO_TRADE first-class."
        )

    # Persist candidate config for audit only — default StrategyConfig stays unless GO
    # and changes demonstrably help TEST (not just ALL).
    if any(c.get("field") != "(none)" for c in proposed_changes):
        cfg_path = BACKEND_ROOT / "app" / "strategy" / "config_real_recal.json"
        payload = proposed_cfg.model_dump()
        payload["_phase_11_6_note"] = (
            "Candidate only. Adopt as default only if GO and TEST improves vs baseline; "
            "otherwise keep StrategyConfig defaults."
        )
        payload["_gate_decision"] = decision
        cfg_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _log(f"Wrote {cfg_path}")
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "comparison": {
            "original_11_5_ref": original_ref,
            "expanded_pre_recal_all": baseline_all,
            "expanded_pre_recal_test": baseline_test,
            "expanded_post_recal_all": post_all,
            "expanded_post_recal_validation": post_val,
            "expanded_post_recal_test": post_test,
        },
        "applied_changes": proposed_changes,
        "phase10_test": {
            "rule_only_test": post_test,
            "note": (
                "RULE_ONLY on held-out TEST with full-series warmup context. "
                "ML_FILTER omitted here when no stable real-data edge claimed."
            ),
        },
        "decision": decision,
        "decision_text": decision_text,
    }
    rpath = write_results(results)
    _log(f"Wrote {rpath}")
    _log(f"DECISION: {decision}")
    _log(decision_text)
    return 0 if decision == "GO" else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
