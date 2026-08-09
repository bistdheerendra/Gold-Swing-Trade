# Phase 11.7 — Diagnosis Review (Pre–Rule-Revision Gate)

**Generated:** 2026-08-09  
**Inputs:** `docs/phase-11.6-diagnosis.md`, `docs/phase-11.6-recalibration-results.md`, Phase 6 `docs/strategy.md`  
**Code changes in this phase:** **None** (Step 2 gated to no-code path)

---

## Step 1 — Plain-language diagnosis

### 1. What exactly is failing?

Expectancy is weak/unstable for **both** reasons, not just one:

| Slice | n | Win rate | Expectancy | Profit factor | Reading |
|-------|---|----------|------------|---------------|---------|
| Expanded ALL (pre-recal) | 34 | 38.2% | **+0.07R** | 1.10 | Barely above water |
| Held-out TEST | 6 | 33.3% | **−0.39R** | 0.55 | Losing; winners do not cover losers |
| Phase 11.5 small window | 12 | 33.3% | **−0.19R** | — | Same story, smaller n |

Context for a `min_rr=1.5` design: rough breakeven win rate if winners reliably realize ~1.5R and losers ~−1R is about **40%**. Observed win rates are **33–38%** — already on the wrong side of that line unless average wins are well above 1.5R.

- On **ALL**, PF ≈ 1.10 says wins barely outweigh losses — edge is noise-level, not a clear R:R success.
- On **TEST**, PF ≈ 0.55 with WR 33% says **reward realization is too weak relative to losses** *and* win rate is too low.

So: not “only win rate” and not “only R:R” — **both**, with held-out evidence pointing especially at poor payoff when the few trades fire.

### 2. How real PAXGUSD diverges from Phase 6 assumptions

Numbers from Phase 11.6 TRAIN+VAL diagnosis sample (n=80 scored points; TEST untouched):

| Signal | Real distribution | Phase 6 / MTF assumption | Divergence |
|--------|-------------------|--------------------------|------------|
| **Trend vs chop (ADX)** | p10=16.1, **p50=23.3**, p90=40.7 | MTF uses ADX ≥ ~20 as trend filter | About half the time ADX is only *mildly* trending; not a strong persistent trend regime |
| **RSI** | p10=34.4, **p50=49.1**, p90=66.8 | Bull/bear bias often uses RSI ≥55 / ≤45 | Real RSI sits near **neutral** most of the time — directional RSI bias fires less often than a trending-gold narrative assumes |
| **ATR% (15m)** | p10=0.04%, **p50=0.16%**, p90=0.29% | Synthetic-era relative moves were larger vs mock price paths | Real PAXGUSD at ~4340 is **quiet in %-terms**; SL/TP ATR buffers and “high vol” penalties were shaped in a different vol world |
| **Score bands** | 50–64: 37/80 (46%); ≥65: 39/80; ≥80: 6/80 | Signal at ≥65, WAIT 50–64 | Scores **do** reach 65+ often enough — the gate is reachable; problem is not “scores never clear 65” |
| **Direction mix (diagnose sample)** | NO_TRADE 42, WAIT 36, SELL 2, BUY 0 | Swing system expects occasional clean BUY/SELL | Sampled moments are **WAIT/NO_TRADE dominant** — consistent with ranging/neutral gold, not constant SMC confluence |

**Top blockers when score is already high** (Phase 11.6):

1. Location / dealing zone (DISCOUNT/PREMIUM/equilibrium) — 19 mentions  
2. Entry TF confirmation incomplete — 8  
3. All MTF layers oppose proposed direction — 6  
4. RR below `min_rr` 1.5 — 3  
5. Not near active OB/zone — 3  
6. Elevated ATR — 3  

That pattern is **suggestive** of confluence + location + RR structure friction — but it is **not** a controlled experiment proving which one causes negative TEST expectancy.

History depth: Delta PAXGUSD max window starts ~**2026-02-19** → ~16k 15m bars, ~172 daily bars. That is the API ceiling today, not a truncated download.

### 3. Threshold problem vs structural problem?

**Threshold recalibration already failed (Phase 11.6):**

- `signal_threshold` / `wait_threshold` were **not** lowered (p90 score = 76 ≥ 65 — gate was reachable).
- Only candidate change (`high_volatility_penalty` 8→5) **worsened** ALL expectancy (+0.07 → +0.01) and left TEST unchanged (−0.39R).

So this is **not** “wrong numbers in an otherwise proven formula.”

Does that prove the **rule combination logic** is wrong?

**Not cleanly.** Evidence is consistent with several stories at once:

| Story | Supported? | Caveat |
|-------|------------|--------|
| Too many confluences / location hard-filters | Partially (blocker counts) | Changing them without more trades = guesswork |
| HTF alignment / MTF opposition too strict | Partially (6 “all layers oppose”) | May be correctly rejecting bad trades |
| SL/TP / RR structure too optimistic vs real paths | Partially (TEST PF 0.55; RR-below-min blocks) | n=6 cannot localize SL vs TP vs entry |
| Gold at these TFs simply rarely offers clean swings in this listing window | Plausible (WAIT/NO_TRADE dominance, neutral RSI, mild ADX) | Needs more calendar time or another instrument |
| Sample too small to trust any structural rewrite | **Yes — primary finding** | See §4 |

**Explicit statement:** Phase 11.6 evidence does **not** clearly support a single structural rewrite target. Inventing “remove HTF hard alignment” or “relax location” as *the* fix would be narrative, not diagnosis.

### 4. Sample size honesty check

| Dataset | Trades | Enough to trust a structural change? |
|---------|--------|--------------------------------------|
| ALL expanded | **34** | Barely enough to say “weak / unstable,” **not** enough to A/B rule variants |
| Held-out TEST | **6** | **No** — two or three outcomes dominate the metric |
| Delta history left on the table | **None** for PAXGUSD | Max available window already used |

**Conclusion:** More history is **not available today** from Delta India for this product. Waiting for the listing to age, or evaluating a longer XAUUSD series as a *separate* research track, are the honest ways to grow n — not rewriting confluence on 34 trades.

---

## Step 2 — Decision gate

**Outcome: NO structural rule-logic revision in Phase 11.7.**

Reason: the binding constraint is **evidence insufficiency / sample thinness**, not a diagnosed, localized structural defect. Forcing Step 3 would repeat Phase 11.6’s mistake at a larger blast radius (harder to undo, easier to overfit).

### Non-code next steps (proposed)

1. **Collect more real PAXGUSD history** as Delta listing ages; re-run expanded backtest periodically (same protocol, no test peeking while iterating).
2. **Optional parallel research:** longer **XAUUSD** history (Twelve Data) as a *reference* study — do **not** blend with Delta PAXGUSD or treat it as the same instrument.
3. **Deeper trade autopsy (read-only):** when re-running backtests, export per-trade `average_win_r` / `average_loss_r` / exit reasons so win-rate vs R:R is measured, not reverse-engineered — still without changing rules until n is larger.
4. **Only then** reopen Step 3 if a specific structural hypothesis is supported by blocker + trade-outcome evidence on TRAIN/VAL with a defendable sample.

---

## Step 3 — Skipped

No Phase 6 rule combination changes. Default `StrategyConfig` 1.0.0 unchanged. Held-out TEST **not** re-touched in this phase.

---

## Step 4 — Final gate

**NO-GO for Phase 12** (unchanged from Phase 11.6; reinforced).

Do not start paper trading. Do not rewrite rules on this sample. Prefer data accumulation and honest re-measurement.
