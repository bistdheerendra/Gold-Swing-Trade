# ML Candle-Level Labeling (Phase 11.8)

**Status:** Research artifact — does **not** feed Phase 6 / Phase 10 until a later explicit wire-up.  
**Label version:** `2.0.0-triple-barrier`  
**Dataset family:** `data/ml_datasets_candle/` (separate from Phase 8 `data/ml_datasets/`)

> **A priori constants** (chosen *before* looking at held-out test model metrics):
>
> | Constant | Value | Reasoning |
> |----------|-------|-----------|
> | `TRIPLE_BARRIER_HORIZON_BARS` (`N`) | **8** | On 15m candles, 8 bars ≈ **2 hours** — short swing / session continuation horizon without requiring multi-day outcomes on a thin listing history |
> | `TRIPLE_BARRIER_ATR_MULT` (`k`) | **1.0** | One ATR of favorable excursion before adverse is a standard, unoptimized barrier width. Real PAXGUSD 15m ATR% median ≈ 0.16% (Phase 11.7), so `k=1` adapts barriers to local volatility instead of a fixed %-threshold tuned on synthetic data |
> | `TRIPLE_BARRIER_ATR_PERIOD` | **14** | Classic Wilder ATR period; matches TA engine default |
> | Same-bar both-touch | **FLAT** | Conservative: do not invent UP/DOWN when both barriers print in one candle |
> | Vertical barrier | **FLAT** | If neither horizontal barrier is hit within `N` bars → FLAT |

Do **not** retune `N` / `k` after seeing test scores.

---

## Label definition (triple barrier)

For each eligible candle at index `t` with close `C_t`:

1. Compute **Wilder ATR(14)** using only bars `0..t` (causal). Call it `ATR_t`.
2. If `ATR_t` is missing or ≤ 0 → no label (row skipped / truncated).
3. Horizontal barriers:
   - Upper: `C_t + k × ATR_t`
   - Lower: `C_t − k × ATR_t`
4. Scan future bars `t+1 … t+N` **in order** (label may use the future; features may not):
   - If `high ≥ upper` and `low ≤ lower` on the **same** bar → **`FLAT`**
   - Else if `high ≥ upper` → **`UP`**
   - Else if `low ≤ lower` → **`DOWN`**
5. If neither horizontal barrier is touched by `t+N` → **`FLAT`**

Primary training target: `direction` ∈ `{UP, DOWN, FLAT}`.

Auxiliary labels (optional, same builder): `tb_horizon=N`, `tb_atr_mult=k`, `tb_atr=ATR_t` for audit.

This **replaces** Phase 8’s sparse `strategy_outcome` / rule-triggered labels for this dataset family. Phase 8 trade-outcome datasets remain on disk untouched.

---

## Features

Same Phase 8 causal feature set (TA / SMC / MTF / price / volatility / time), computed as of candle `t` only.

- `include_strategy=False` for candle-level builds (strategy features are not required for this research track and dominate CPU).
- Nothing after `t` enters features.

---

## Chronological split

Same ratios as Phase 8 / Phase 11.6 backtests: **70% train / 15% validation / 15% test**, chronological, never shuffled.

On the max Delta India PAXGUSD 15m window (~2026-02-19 → latest, ~16 382 bars), labeled rows ≈ **16 294** after warmup/horizon trim:

| Split | Approx. dates (Phase 11.8 run) | n |
|-------|--------------------------------|---|
| TRAIN | 2026-02-20 → 2026-06-19 | 11405 |
| VALIDATION | 2026-06-19 → 2026-07-14 | 2444 |
| TEST | 2026-07-14 → 2026-08-09 | 2445 |

Exact ISO ranges live in each run’s `dataset_metadata.json` and `docs/phase-11.8-candle-ml-results.md`.

---

## Full history (not UI `bar_limit=220`)

The ML Dataset UI default `bar_limit=220` is for **preview only**. Phase 11.8 builds must load **all** available `data/historical/PAXGUSD_*.csv` bars (or equivalent provider backfill), with `limit` ≥ full series length — never the UI preview cap.

Output root: `data/ml_datasets_candle/<dataset_id>/`  
Artifacts: `artifacts/ml_candle/<target>/<model_id>/`

---

## Class imbalance

On the Phase 11.8 full-history run (`N=8`, `k=1.0`), measured distribution was approximately:

| Class | Share (all rows) |
|-------|------------------|
| DOWN | ~45.5% |
| UP | ~42.4% |
| FLAT | ~12.1% |

**FLAT did not dominate** under these a priori barriers (1×ATR within 8 bars is often reached). That differs from the Phase 11.7 *expectation* that a low-ADX regime would yield mostly FLAT — the expectation was recorded honestly; the measured outcome is also recorded honestly. Do **not** retune `k`/`N` on TEST to force more FLAT or prettier metrics.

Always compare models to a **majority-class baseline**. Accuracy alone is not skill.
