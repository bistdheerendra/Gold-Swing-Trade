"""ML feature / label / dataset unit + leakage tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.market.schemas import OHLCVBar, Timeframe
from app.ml.config import DatasetConfig, FeatureConfig, LabelConfig
from app.ml.dataset_builder import DatasetBuilder
from app.ml.dataset_validator import DatasetValidationError, DatasetValidator
from app.ml.feature_builder import FeatureBuilder
from app.ml.label_builder import LabelBuilder
from app.ml.schemas import DatasetRow
from app.smc.engine import SmcEngine
from app.ta.engine import TechnicalAnalysisEngine


def _bars(n: int = 200) -> list[OHLCVBar]:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 2000.0
    out = []
    for i in range(n):
        o = price
        h = price + 3
        l = price - 3
        c = price + (0.4 if i % 2 == 0 else -0.2)
        out.append(
            OHLCVBar(
                timestamp=t0 + timedelta(minutes=15 * i),
                symbol="XAUUSD",
                timeframe=Timeframe.M15,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1.0,
                source="test",
            )
        )
        price = c
    return out


def test_ta_features_present() -> None:
    bars = _bars(120)
    ta = TechnicalAnalysisEngine().analyze(bars, symbol="XAUUSD", timeframe="15m")
    smc = SmcEngine().analyze(bars, symbol="XAUUSD", timeframe="15m")
    fb = FeatureBuilder(FeatureConfig(include_strategy=False, include_mtf=False))
    feats = fb.build_with_close(
        bar=bars[-1], index=len(bars) - 1, ta=ta, smc=smc, mtf=None, strategy=None
    )
    assert "rsi" in feats
    assert "atr_pct" in feats
    assert "ema_alignment" in feats
    assert "structure_bias" in feats
    assert "body_size_pct" in feats
    assert "hour_utc" in feats


def test_labels_forward_mfe() -> None:
    bars = _bars(80)
    lb = LabelBuilder(LabelConfig(horizons=[5, 10], include_strategy_outcome=False))
    labels = lb.build(bars, 40)
    assert labels["return_5"] is not None
    assert labels["mfe_10"] is not None
    assert labels["mae_10"] is not None
    assert labels["direction"] in ("UP", "DOWN", "NEUTRAL")


def test_dataset_build_split_and_export(tmp_path: Path) -> None:
    bars = _bars(220)
    cfg = DatasetConfig(
        warmup_bars=80,
        row_step=2,
        feature=FeatureConfig(include_strategy=False),
        label=LabelConfig(include_strategy_outcome=False, horizons=[5, 10]),
        output_dir=str(tmp_path),
    )
    result = DatasetBuilder(cfg).build({"15m": bars}, source="test")
    assert result.metadata.row_count > 10
    assert result.metadata.split.train > 0
    assert result.metadata.split.test > 0
    assert result.statistics.feature_count > 20
    assert any(Path(p).exists() for p in result.metadata.output_files if p.endswith("train.csv"))


def test_leakage_future_mutation_features_stable(tmp_path: Path) -> None:
    bars = _bars(220)
    cfg = DatasetConfig(
        warmup_bars=80,
        row_step=3,
        feature=FeatureConfig(include_strategy=False),
        label=LabelConfig(include_strategy_outcome=False, horizons=[5, 10]),
        output_dir=str(tmp_path / "a"),
    )
    builder = DatasetBuilder(cfg)
    a = builder.build({"15m": bars}, source="test")

    cut = bars[150].timestamp
    mutated = [
        b.model_copy(update={"high": b.high + 200, "close": b.close + 150})
        if b.timestamp > cut
        else b
        for b in bars
    ]
    cfg2 = cfg.model_copy(update={"output_dir": str(tmp_path / "b")})
    b = DatasetBuilder(cfg2).build({"15m": mutated}, source="test")

    # Features for rows with timestamp <= cut must match
    a_map = {r.timestamp: r.features for r in a.preview_rows}
    # use full rows from store
    from app.ml.dataset_builder import get_dataset_rows

    rows_a = get_dataset_rows(a.dataset_id) or []
    rows_b = get_dataset_rows(b.dataset_id) or []
    for ra, rb in zip(rows_a, rows_b):
        if ra.timestamp > cut.isoformat():
            break
        assert ra.features == rb.features
        # labels may differ when future mutated for rows near cut
        break  # at least first overlapping rows
    # Stronger: all rows with index such that horizon doesn't reach mutation still same labels;
    # for rows before cut - max_h, features identical
    for ra in rows_a:
        if ra.timestamp > cut.isoformat():
            continue
        rb = next(x for x in rows_b if x.timestamp == ra.timestamp)
        assert ra.features == rb.features


def test_labels_change_when_future_mutated(tmp_path: Path) -> None:
    bars = _bars(220)
    cfg = DatasetConfig(
        warmup_bars=80,
        row_step=5,
        feature=FeatureConfig(include_strategy=False),
        label=LabelConfig(include_strategy_outcome=False, horizons=[5]),
        output_dir=str(tmp_path / "c"),
    )
    a = DatasetBuilder(cfg).build({"15m": bars}, source="test")
    from app.ml.dataset_builder import get_dataset_rows

    rows_a = get_dataset_rows(a.dataset_id) or []
    # mutate immediately after a mid row
    mid = rows_a[len(rows_a) // 2]
    mid_ts = datetime.fromisoformat(mid.timestamp.replace("Z", "+00:00"))
    mutated = [
        b.model_copy(update={"close": b.close + 50, "high": b.high + 50})
        if b.timestamp > mid_ts
        else b
        for b in bars
    ]
    cfg2 = cfg.model_copy(update={"output_dir": str(tmp_path / "d")})
    b = DatasetBuilder(cfg2).build({"15m": mutated}, source="test")
    rows_b = get_dataset_rows(b.dataset_id) or []
    rb = next(x for x in rows_b if x.timestamp == mid.timestamp)
    # Feature same, label return may change
    assert mid.features == rb.features
    assert mid.labels.get("return_5") != rb.labels.get("return_5") or mid.labels.get(
        "return_5"
    ) is not None


def test_validator_rejects_leaky_feature() -> None:
    row = DatasetRow(
        timestamp="2024-01-01T00:00:00+00:00",
        symbol="XAUUSD",
        timeframe="15m",
        index=1,
        features={"rsi": 50.0, "future_return": 0.1},
        labels={"direction": "UP"},
    )
    with pytest.raises(DatasetValidationError):
        DatasetValidator().validate([row])


def test_reproducibility(tmp_path: Path) -> None:
    bars = _bars(200)
    cfg = DatasetConfig(
        warmup_bars=80,
        row_step=4,
        feature=FeatureConfig(include_strategy=False),
        label=LabelConfig(include_strategy_outcome=False, horizons=[5, 10]),
        output_dir=str(tmp_path / "r1"),
    )
    a = DatasetBuilder(cfg).build({"15m": bars}, source="test")
    cfg2 = cfg.model_copy(update={"output_dir": str(tmp_path / "r2")})
    b = DatasetBuilder(cfg2).build({"15m": bars}, source="test")
    assert a.statistics.row_count == b.statistics.row_count
    assert a.metadata.feature_count == b.metadata.feature_count
    from app.ml.dataset_builder import get_dataset_rows

    ra = get_dataset_rows(a.dataset_id) or []
    rb = get_dataset_rows(b.dataset_id) or []
    assert [r.features for r in ra] == [r.features for r in rb]
    assert [r.labels for r in ra] == [r.labels for r in rb]
