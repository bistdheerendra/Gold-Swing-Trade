# Gold Swing AI — Monitoring Checklist (Post Phase 11.11)

**Purpose:** Since the current NO-GO for Phase 12 is driven mainly by thin real-data
sample size and a currently quiet/low-trend PAXGUSD market — not by a fixable bug —
the right next step is patience, not more code changes. This checklist defines
*when* and *how* to recheck, so re-evaluation is systematic instead of ad-hoc.

**Baseline doc:** [phase-11.11-post-fix-backtest.md](phase-11.11-post-fix-backtest.md)  
**Repro script:** `backend/scripts/phase_11_11_post_fix_backtest.py` (same methodology; extend window only)

---

## Current baseline (as of Phase 11.11, 2026-08)

| Metric | Value |
|--------|-------|
| Real history available | ~2026-02-19 → present (~16,382 × 15m candles) |
| Total backtest trades (ALL) | 53 |
| Expectancy (ALL) | +0.070R (~breakeven, not trustworthy) |
| TEST slice trades | 9 (too thin to trust alone) |
| Max drawdown (TRAIN+VAL) | 11.4% |
| Market regime | Quiet — ADX p50 ≈ 23, ATR% p50 ≈ 0.16% |
| ML candle-level lift | +2.7pp over majority baseline (weak) |
| Phase 12 status | **NO-GO** |

---

## Recheck cadence

**Every 4 weeks**, or sooner if a clear regime change is visible on the chart
(e.g. a sustained multi-day trending move), do a lightweight recheck using the
steps below. Don't re-run full Phase 11.6-style investigations every time — only
escalate to a full re-diagnosis when the lightweight recheck shows a meaningful
shift (see thresholds below).

Append each recheck to [recheck-log.md](recheck-log.md).

---

## Lightweight recheck steps (~15–20 min)

1. **Extend / refresh Delta PAXGUSD CSVs** if needed (`data/historical/PAXGUSD_*.csv`), then
   **re-run the Phase 11.11 backtest methodology** on the current full history
   (same thresholds, same SL-fix logic — only the date range grows)
2. Record: trade count, expectancy (R), profit factor, max drawdown — same table
   format as [phase-11.11-post-fix-backtest.md](phase-11.11-post-fix-backtest.md)
3. Check market regime stats: current ADX percentile, ATR% percentile — compare
   to the quiet baseline above
4. Note trade count growth: how many *new* trades has the extra month of data added?

Suggested command (from `backend/`, after CSV refresh):

```text
.\.venv\Scripts\python.exe scripts/phase_11_11_post_fix_backtest.py
```

Or a focused ALL / TEST pass if a thinner script is added later — keep splits,
steps (`ALL`/`TRAIN+VAL` step=24, `TEST` step=12), and default `StrategyConfig` 1.0.0 unchanged.

---

## Escalation thresholds — when to do a full re-diagnosis

Only trigger a deeper Phase-11.6-style investigation when **any one** of these is true:

- [ ] Total backtest trade count has grown past **~80–100** (meaningfully larger
      than the current 53, enough to trust a result with more confidence)
- [ ] ALL-slice expectancy has moved clearly positive (e.g. beyond +0.15R) **and**
      held for two consecutive monthly rechecks (not just one lucky month)
- [ ] Market regime has shifted — ADX p50 rises meaningfully above ~23 for a
      sustained period (real trending conditions returning)
- [ ] A new structural bug is found (like the SL geometry issue in Phase 11.11) —
      fix it, then treat that fix's backtest re-run as its own checkpoint

---

## What NOT to do between rechecks

- Don't tune thresholds "just to see" between scheduled rechecks — this creates
  the exact overfitting risk Phase 11.6/11.9 were designed to avoid
- Don't start Phase 12 based on a single good-looking monthly number — require
  the two-consecutive-recheck confirmation above
- Don't blend XAUUSD data into the PAXGUSD decision pipeline (PAXGUSD is the only
  instrument that matters for the trading GO/NO-GO)

---

## Quick log template (copy for each recheck)

```text
Recheck date: 2026-__-__
History window: 2026-02-19 → 2026-__-__
Trade count (ALL): __
Expectancy (ALL, R): __
Profit factor: __
Max drawdown %: __
ADX p50 (recent window): __
ATR% p50 (recent window): __
Escalation triggered? Y/N — which threshold: __
Notes: __
```

Paste filled entries into [recheck-log.md](recheck-log.md).

---

## Bottom line

Nothing to build right now. The system is honest and working correctly — it's
telling you the strategy isn't proven yet, not that something is broken. Revisit
on the cadence above, and only escalate when the data actually earns it.
