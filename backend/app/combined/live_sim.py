"""Research live-like sequential simulator (no look-ahead)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence

from app.combined.config import CombinedSignalConfig
from app.combined.engine import CombinedSignalEngine
from app.combined.schemas import CombinedSignalResult
from app.market.schemas import OHLCVBar, ensure_utc
from app.mtf.sync import candle_close_time
from app.strategy.config import StrategyConfig
from app.strategy.engine import SignalStore


class ResearchLiveSimulator:
    """
    Process entry bars sequentially. At each timestamp:
    update window → rule → ML → combine → record.
    Never looks ahead.
    """

    def __init__(
        self,
        config: Optional[CombinedSignalConfig] = None,
        *,
        strategy_config: Optional[StrategyConfig] = None,
        warmup_bars: int = 80,
        step: int = 1,
        mode: str = "ML_FILTER",
    ) -> None:
        self.config = config or CombinedSignalConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.warmup_bars = warmup_bars
        self.step = max(1, step)
        self.mode = mode

    def run(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        symbol: str = "XAUUSD",
        entry_tf: str = "15m",
        model_id: Optional[str] = None,
    ) -> List[CombinedSignalResult]:
        entry = list(bars_by_tf.get(entry_tf) or [])
        engine = CombinedSignalEngine(
            config=self.config,
            strategy_config=self.strategy_config,
            store=SignalStore(),
        )
        if self.mode != "RULE_ONLY":
            engine.ensure_model(model_id)

        out: List[CombinedSignalResult] = []
        for i, bar in enumerate(entry):
            if i < self.warmup_bars:
                continue
            if (i - self.warmup_bars) % self.step != 0:
                continue
            windowed = {
                tf: [b for b in series if ensure_utc(b.timestamp) <= ensure_utc(bar.timestamp)]
                for tf, series in bars_by_tf.items()
            }
            as_of = candle_close_time(bar, entry_tf)
            result = engine.analyze(
                windowed,
                symbol=symbol,
                as_of=as_of,
                model_id=model_id,
                mode=self.mode,
            )
            out.append(result)
        return out
