"""Technical analysis engine — deterministic, causal computations."""

from __future__ import annotations

from typing import List, Optional, Sequence

from app.market.schemas import OHLCVBar
from app.ta import indicators as ind
from app.ta.schemas import (
    LatestIndicators,
    TechnicalAnalysisConfig,
    TechnicalAnalysisResult,
)
from app.ta.structure import structure_snapshot


class TechnicalAnalysisEngine:
    """
    Computes indicators + market structure from OHLCV.

    Critical: as_of_index truncates the working series so no future bars
    participate in the calculation for that snapshot.
    """

    def __init__(self, config: Optional[TechnicalAnalysisConfig] = None) -> None:
        self.config = config or TechnicalAnalysisConfig()

    def analyze(
        self,
        bars: Sequence[OHLCVBar],
        *,
        symbol: str,
        timeframe: str,
        as_of_index: Optional[int] = None,
    ) -> TechnicalAnalysisResult:
        if not bars:
            raise ValueError("bars must be non-empty")

        end = len(bars) - 1 if as_of_index is None else as_of_index
        if end < 0 or end >= len(bars):
            raise ValueError("as_of_index out of range")

        # Truncate — absolute look-ahead guard
        window = list(bars[: end + 1])
        closes = [b.close for b in window]
        highs = [b.high for b in window]
        lows = [b.low for b in window]
        cfg = self.config

        ema_map = {p: ind.ema(closes, p) for p in cfg.ema_periods}
        rsi_vals = ind.rsi(closes, cfg.rsi_period)
        macd_pack = ind.macd(closes, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
        adx_pack = ind.adx(highs, lows, closes, cfg.adx_period)
        atr_vals = ind.atr(highs, lows, closes, cfg.atr_period)
        bb = ind.bollinger_bands(closes, cfg.bb_period, cfg.bb_std)
        structure = structure_snapshot(
            highs,
            lows,
            left=cfg.swing_left,
            right=cfg.swing_right,
            as_of_index=end,
        )

        series: dict[str, List[Optional[float]]] = {
            **{f"ema_{p}": ema_map[p] for p in cfg.ema_periods},
            "rsi": rsi_vals,
            "macd": macd_pack["macd"],
            "macd_signal": macd_pack["signal"],
            "macd_histogram": macd_pack["histogram"],
            "adx": adx_pack["adx"],
            "plus_di": adx_pack["plus_di"],
            "minus_di": adx_pack["minus_di"],
            "atr": atr_vals,
            "bb_mid": bb["mid"],
            "bb_upper": bb["upper"],
            "bb_lower": bb["lower"],
        }

        latest = LatestIndicators(
            ema_20=_last(ema_map.get(20)),
            ema_50=_last(ema_map.get(50)),
            ema_100=_last(ema_map.get(100)),
            ema_200=_last(ema_map.get(200)),
            rsi=_last(rsi_vals),
            macd=_last(macd_pack["macd"]),
            macd_signal=_last(macd_pack["signal"]),
            macd_histogram=_last(macd_pack["histogram"]),
            adx=_last(adx_pack["adx"]),
            plus_di=_last(adx_pack["plus_di"]),
            minus_di=_last(adx_pack["minus_di"]),
            atr=_last(atr_vals),
            bb_mid=_last(bb["mid"]),
            bb_upper=_last(bb["upper"]),
            bb_lower=_last(bb["lower"]),
        )

        as_of_ts = window[-1].timestamp.isoformat()
        return TechnicalAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            bar_count=len(window),
            as_of_index=end,
            as_of_timestamp=as_of_ts,
            latest=latest,
            series=series,
            structure=structure,
            config=cfg,
        )


def _last(values: Optional[List[Optional[float]]]) -> Optional[float]:
    if not values:
        return None
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None
