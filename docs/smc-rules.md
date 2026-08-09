# SMC Rules — Gold Swing AI

**Phase:** 4  
**Status:** Binding specification for the SMC engine  
**Principle:** An event exists at candle `t` only if it could be known after candle `t` has closed. No future bars.

All indices are 0-based positions in a single-timeframe OHLCV series truncated to `as_of_index` inclusive before any detector runs.

---

## 0. Shared conventions

### Direction
- `BULLISH` / `BEARISH`

### Common event fields
Every SMC event carries:
- `id` — stable string `{type}:{timeframe}:{confirm_index}:{source_key}`
- `type` — enum event type
- `direction`
- `timeframe`
- `created_index` — earliest bar involved in formation
- `confirm_index` — first bar index at which the event is known
- `valid` — currently valid (not invalidated)
- `metadata` — typed extras

### Configuration object (`SmcConfig`)
All thresholds live here. Detectors must not hard-code trading assumptions.

| Key | Default | Meaning |
|-----|---------|---------|
| `swing_left` | 2 | Bars left of pivot that must be strictly weaker |
| `swing_right` | 2 | Bars right of pivot required for confirmation |
| `break_on_close` | true | BOS/CHoCH uses close vs level |
| `break_on_wick` | false | If true (and close rule false), use high/low |
| `min_break_distance` | 0.0 | Absolute price beyond level required |
| `min_break_percentage` | 0.0 | Percent of level (level * pct/100) beyond level |
| `fvg_min_size` | 0.0 | Minimum gap size to keep |
| `ob_lookback` | 10 | Candles searched before displacement for OB |
| `ob_min_body_ratio` | 0.5 | body / range minimum |
| `ob_require_bos` | true | OB only after a confirmed BOS |
| `ob_displacement_atr_mult` | 0.0 | Optional ATR filter (0 = disabled) |
| `liq_cluster_tolerance` | 0.15 | Absolute price cluster window |
| `liq_min_touches` | 2 | Min swings to form a liquidity pool |
| `liq_lookback_swings` | 20 | Max recent swings considered |
| `sweep_min_penetration` | 0.0 | Min pierce beyond liquidity |
| `sweep_require_close_reclaim` | true | Close must reclaim level |
| `sweep_max_bars_for_reclaim` | 3 | Bars after pierce to reclaim |
| `eq_band_pct` | 0.02 | ±band around 50% counts as EQUILIBRIUM |

---

## 1. Swing High / Swing Low

**Identical to Phase 3 fractal definition** (reused from `app.ta.structure`).

### Swing High at pivot `i`
Exists only when `confirm_index = i + swing_right <= as_of_index`, and:
- `high[i] > max(high[i-left : i])`
- `high[i] > max(high[i+1 : i+right+1])`

Store: `pivot_index`, `confirm_index`, `price=high[i]`, `timeframe`.

### Swing Low at pivot `i`
Symmetric with lows.

**Availability:** event not present for any `t < confirm_index`.

HH / HL / LH / LL labels compare consecutive confirmed swings of the same type only.

---

## 2. Break of Structure (BOS)

### State inputs
Only **confirmed** swing highs/lows with `confirm_index <= t`.

### Break test at bar `t` against level `L`
Let `buffer = max(min_break_distance, |L| * min_break_percentage / 100)`.

- If `break_on_close`:
  - Bullish break: `close[t] > L + buffer`
  - Bearish break: `close[t] < L - buffer`
- Else if `break_on_wick`:
  - Bullish: `high[t] > L + buffer`
  - Bearish: `low[t] < L - buffer`
- Else: treat as close rule

### Bullish BOS
Continuing bullish structure (bias bullish, or first bullish continuation break):
- Let `SH` = most recent confirmed swing high not yet consumed.
- At first bar `t >= SH.confirm_index` where bullish break vs `SH.price` succeeds:
  - Emit BOS bullish: `break_index=t`, `confirm_index=t`, `broken_level=SH.price`, `source_swing_index=SH.pivot_index`.

### Bearish BOS
Symmetric vs most recent unbroken confirmed swing low.

### Invalid break
If wick pierces but close rule fails (`break_on_close=true`) → **no BOS**.

Each level broken at most once (first confirming bar wins).

---

## 3. Change of Character (CHoCH) — state machine

CHoCH is **not** a renamed BOS. It marks the **first** structural break **against** the active trend bias.

### Bias state
```
bias ∈ {BULLISH, BEARISH, NEUTRAL}

Initialize NEUTRAL until structure establishes:
  - Last two swing highs = HH AND last two swing lows = HL → BULLISH
  - Last two swing highs = LH AND last two swing lows = LL → BEARISH
  - Else NEUTRAL

On BULLISH BOS → bias = BULLISH
On BEARISH BOS → bias = BEARISH
On CHoCH → bias flips to the CHoCH direction
```

### Bullish CHoCH
When `bias == BEARISH`: first bullish break of the protecting confirmed swing high.  
Emits CHoCH (not BOS). Later breaks in the new direction are BOS.

### Bearish CHoCH
When `bias == BULLISH`: first bearish break of the protecting confirmed swing low.

### Sideways / invalid
Mixed labels with NEUTRAL and no clear opposing break → no CHoCH.  
Pure sideways (no break) → no CHoCH.

### Repeated breaks
After a level is consumed by BOS or CHoCH, further touches do not re-emit.

---

## 4. Fair Value Gap (3-candle)

Candles `i-2`, `i-1`, `i` with `i` closed (`i <= as_of_index`).

### Bullish FVG
`low[i] > high[i-2]`
- Gap: `low = high[i-2]`, `high = low[i]`, `size = high - low`
- Keep if `size >= fvg_min_size`
- `created_index = i`, `confirm_index = i`

### Bearish FVG
`high[i] < low[i-2]`
- Gap: `high = low[i-2]`, `low = high[i]`

### Lifecycle
| State | Rule |
|-------|------|
| CREATED / ACTIVE | No fill yet |
| PARTIALLY_FILLED | Later bar intersects gap without full traverse |
| FILLED / INVALIDATED | Bullish: `low[t] <= gap.low`; Bearish: `high[t] >= gap.high` |

`fill_index` = first `t > created_index` meeting FILLED.  
Available from `confirm_index` only.

---

## 5. Order Block

**Chosen definition (one of many SMC variants — configurable):**

### Bullish OB
After bullish BOS at `t_bos`:
1. Search `(t_bos - ob_lookback, t_bos)` for bearish candles (`close < open`).
2. Qualifying: `body_ratio = |close-open| / max(high-low, ε) >= ob_min_body_ratio`.
3. Last qualifying bearish candle → zone `[low, high]`.
4. `origin_index` = candle; `confirmation_index` = `t_bos`.
5. If `ob_require_bos` and no BOS → no OB.

### Bearish OB
Last bullish candle before bearish BOS.

### Mitigation
- Bullish: first `t > confirmation_index` with `low[t] <= ob.low`
- Bearish: first `t > confirmation_index` with `high[t] >= ob.high`

`strength = min(1.0, body_ratio)`.

---

## 6. Demand / Supply Zones

Phase 4 mapping (deterministic):
- **Demand** = unmitigated bullish OB
- **Supply** = unmitigated bearish OB

Same causal rules as OB. Not every candle.

---

## 7. Liquidity pools

Confirmed swings within `liq_lookback_swings`, `confirm_index <= as_of`.

Cluster if prices differ by `<= liq_cluster_tolerance`.  
Pool requires `>= liq_min_touches` members.

- Buy-side level = max of high-cluster
- Sell-side level = min of low-cluster

Pool `confirm_index` = max member confirm_index.

---

## 8. Liquidity Sweep

### Bearish sweep (buy-side taken)
1. Pierce: `high[t_p] > L + sweep_min_penetration`
2. If reclaim required: within `sweep_max_bars_for_reclaim`, `close[t_c] < L`
3. `sweep_index=t_p`, `confirmation_index=t_c` (or `t_p` if no reclaim)
4. Available only at `confirmation_index`

### Bullish sweep (sell-side taken)
Symmetric.

Pierce without reclaim → no confirmed event.

---

## 9. Premium / Discount / Equilibrium

- `range_high` / `range_low` = last confirmed swing high / low (`confirm_index <= as_of`)
- `equilibrium = (high+low)/2`
- `position = (close[as_of] - low) / (high - low)`
- `EQUILIBRIUM` if `|position - 0.5| <= eq_band_pct`
- `PREMIUM` if `position > 0.5 + eq_band_pct`
- `DISCOUNT` if `position < 0.5 - eq_band_pct`

No unconfirmed future swings.

---

## 10. Multi-timeframe

Detectors run on **one** timeframe. MTF aggregation is Phase 5.

---

## 11. SMC Score (UI only — not a trade signal)

| Component | Points |
|-----------|--------|
| Clear bias | 20 |
| Recent BOS aligned | 20 |
| Active aligned FVG | 15 |
| Active aligned OB | 15 |
| Aligned liquidity sweep | 15 |
| Discount (bull) / Premium (bear) | 15 |

Cap 100. **No BUY/SELL in Phase 4.**

---

## 12. Known limitations

1. OB definition is one ICT/SMC variant.
2. Demand/Supply = OB zones in Phase 4.
3. Liquidity clustering is price-tolerance based.
4. No session/killzone filters.
5. Score is illustrative, not expectancy-optimized.
