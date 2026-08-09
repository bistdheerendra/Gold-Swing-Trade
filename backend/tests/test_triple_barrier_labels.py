"""Unit tests for Phase 11.8 ATR triple-barrier labels."""

from datetime import datetime, timedelta, timezone

from app.market.schemas import OHLCVBar, Timeframe
from app.ml.config import LabelConfig, TripleBarrierConfig, candle_level_dataset_config
from app.ml.label_builder import LabelBuilder, triple_barrier_direction


def _bars(n: int, *, pattern: str = "flat") -> list[OHLCVBar]:
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    out: list[OHLCVBar] = []
    price = 4000.0
    for i in range(n):
        ts = start + timedelta(minutes=15 * i)
        if pattern == "up_burst" and i == 50:
            high, low, close = price + 50, price - 1, price + 40
        elif pattern == "down_burst" and i == 50:
            high, low, close = price + 1, price - 50, price - 40
        elif pattern == "both_burst" and i == 50:
            high, low, close = price + 50, price - 50, price
        else:
            # mild noise so ATR is positive after warmup
            wobble = (i % 5) * 0.2
            high, low, close = price + 1 + wobble, price - 1 - wobble, price + (0.1 if i % 2 else -0.1)
            price = close
        out.append(
            OHLCVBar(
                timestamp=ts,
                symbol="PAXGUSD",
                timeframe=Timeframe.M15,
                open=price,
                high=high,
                low=low,
                close=close,
                volume=1.0,
                source="test",
            )
        )
        price = close
    return out


def test_triple_barrier_up_before_down() -> None:
    bars = _bars(80, pattern="up_burst")
    # label at bar before burst
    idx = 49
    direction, atr_t = triple_barrier_direction(
        bars, idx, TripleBarrierConfig(horizon_bars=8, atr_mult=1.0, atr_period=14)
    )
    assert atr_t is not None and atr_t > 0
    assert direction == "UP"


def test_triple_barrier_down() -> None:
    bars = _bars(80, pattern="down_burst")
    direction, _ = triple_barrier_direction(
        bars, 49, TripleBarrierConfig(horizon_bars=8, atr_mult=1.0, atr_period=14)
    )
    assert direction == "DOWN"


def test_triple_barrier_same_bar_both_is_flat() -> None:
    bars = _bars(80, pattern="both_burst")
    direction, _ = triple_barrier_direction(
        bars, 49, TripleBarrierConfig(horizon_bars=8, atr_mult=0.5, atr_period=14)
    )
    assert direction == "FLAT"


def test_triple_barrier_vertical_flat() -> None:
    bars = _bars(80, pattern="flat")
    direction, _ = triple_barrier_direction(
        bars, 40, TripleBarrierConfig(horizon_bars=8, atr_mult=5.0, atr_period=14)
    )
    assert direction == "FLAT"


def test_triple_barrier_truncated_none() -> None:
    bars = _bars(30, pattern="flat")
    direction, _ = triple_barrier_direction(
        bars, 25, TripleBarrierConfig(horizon_bars=8)
    )
    assert direction is None


def test_label_builder_triple_barrier_mode() -> None:
    bars = _bars(100, pattern="up_burst")
    cfg = LabelConfig(labeling_mode="triple_barrier", include_strategy_outcome=False)
    lb = LabelBuilder(cfg)
    lb.prime_atr(bars)
    labels = lb.build(bars, 49)
    assert labels["direction"] in ("UP", "DOWN", "FLAT")
    assert labels["tb_horizon"] == 8


def test_candle_level_config_defaults() -> None:
    cfg = candle_level_dataset_config()
    assert cfg.label.labeling_mode == "triple_barrier"
    assert cfg.feature.include_strategy is False
    assert cfg.label.include_strategy_outcome is False
    assert cfg.output_dir == "data/ml_datasets_candle"
    assert cfg.label.triple_barrier.horizon_bars == 8
    assert cfg.label.triple_barrier.atr_mult == 1.0
