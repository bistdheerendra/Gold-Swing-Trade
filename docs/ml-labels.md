# ML Labels (v1.0.0 + Phase 11.8)

Labels **may** use future bars. Features must not.

| Label | Definition |
|-------|------------|
| `return_H` | (close[T+H] − close[T]) / close[T] |
| `direction` (legacy) | UP / DOWN / NEUTRAL vs `direction_threshold_pct` on primary horizon |
| `direction` (Phase 11.8) | UP / DOWN / FLAT via ATR triple-barrier — see [ml-labeling.md](ml-labeling.md) |
| `mfe_H` | max favorable excursion over next H bars |
| `mae_H` | max adverse excursion over next H bars |
| `strategy_outcome` | WIN / LOSS / NO_ENTRY / NO_SETUP using Phase 7 execution assumptions |
| `future_R` | R-multiple when strategy outcome resolves |
| `multiclass_outcome` | BUY_WIN / BUY_LOSS / SELL_WIN / SELL_LOSS / NO_SETUP |

Horizons default (legacy): 5, 10, 20, 40 bars. Triple-barrier default: `N=8`, `k=1.0×ATR(14)`.

WAIT / NO_TRADE rows → `NO_SETUP` for strategy_outcome labels (do not force BUY/SELL). Candle-level datasets do **not** gate on Phase 6 fires.

Phase 11.8 datasets are stored under `data/ml_datasets_candle/` and must not overwrite Phase 8 `data/ml_datasets/`.
