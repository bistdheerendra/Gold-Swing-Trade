"""Build a single causal feature row at as_of (same path as Phase 8)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Mapping, Optional, Sequence, Tuple

from app.backtest.engine import resample_ohlcv
from app.market.schemas import ANALYSIS_TIMEFRAMES, OHLCVBar, ensure_utc
from app.ml.feature_builder import FeatureBuilder
from app.mtf.analyzer import MultiTimeframeAnalyzer
from app.mtf.sync import candle_close_time
from app.smc.engine import SmcEngine
from app.strategy.schemas import StrategyAnalyzeResult
from app.ta.engine import TechnicalAnalysisEngine

HTFS = ANALYSIS_TIMEFRAMES


def build_feature_row(
    bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
    *,
    as_of: datetime,
    entry_tf: str = "15m",
    strategy: Optional[StrategyAnalyzeResult] = None,
) -> Tuple[Dict[str, float | int | None], OHLCVBar, int]:
    """
    Point-in-time features using only bars with timestamp <= as_of bar.
    Never fits scalers. Never uses future candles.
    """
    as_of_u = ensure_utc(as_of)
    prepared: Dict[str, list] = {}
    entry = list(bars_by_tf.get(entry_tf) or bars_by_tf.get("15m") or [])
    if not entry:
        raise ValueError("No entry bars")
    for tf in HTFS:
        if tf in bars_by_tf and bars_by_tf[tf]:
            prepared[tf] = list(bars_by_tf[tf])
        else:
            prepared[tf] = resample_ohlcv(entry, tf)

    # Pick last entry bar whose close time <= as_of (or timestamp <= as_of)
    entry_series = prepared.get(entry_tf, entry)
    eligible = [b for b in entry_series if ensure_utc(b.timestamp) <= as_of_u]
    if not eligible:
        raise ValueError("No bars at or before as_of")
    bar = eligible[-1]
    idx = len(eligible) - 1

    windowed = {
        tf: [b for b in series if ensure_utc(b.timestamp) <= ensure_utc(bar.timestamp)]
        for tf, series in prepared.items()
    }
    entry_window = windowed[entry_tf]
    local_idx = len(entry_window) - 1

    ta = TechnicalAnalysisEngine().analyze(entry_window, as_of_index=local_idx)
    smc = SmcEngine().analyze(entry_window, as_of_index=local_idx)
    mtf = MultiTimeframeAnalyzer().analyze(windowed, as_of=candle_close_time(bar, entry_tf))

    features = FeatureBuilder().build_with_close(
        bar=bar,
        index=local_idx,
        ta=ta,
        smc=smc,
        mtf=mtf,
        strategy=strategy,
    )
    return features, bar, idx
